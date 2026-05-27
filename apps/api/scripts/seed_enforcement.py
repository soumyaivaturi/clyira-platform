"""
Enforcement Corpus Seeder
=========================
Populates the enforcement_records table from three public sources:

  1. openFDA Drug Enforcement  — recall/enforcement actions (structured JSON)
  2. openFDA Device Enforcement — MDR/recall enforcement actions
  3. FDA Warning Letters        — scraped from fda.gov RSS + HTML

Usage:
    cd apps/api
    python scripts/seed_enforcement.py                 # all sources, last 3 years
    python scripts/seed_enforcement.py --years 5       # last 5 years
    python scripts/seed_enforcement.py --source fda    # openFDA only
    python scripts/seed_enforcement.py --source wl     # warning letters only
    python scripts/seed_enforcement.py --dry-run       # print records, do not insert

Requires DATABASE_URL env var (or .env file in apps/api/).
"""
import asyncio
import argparse
import logging
import re
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

# Allow running from apps/api/scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.regulatory import EnforcementRecord
from app.models.base import generate_uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_enforcement")


# ── Category taxonomy ─────────────────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "data_integrity": [
        "data integrity", "alcoa", "falsif", "fabricat", "audit trail",
        "electronic record", "chromatogram", "raw data", "backdating",
        "21 cfr 11", "part 11",
    ],
    "process_validation": [
        "process validation", "validation protocol", "cpv", "continued process",
        "ppq", "process performance", "ipc", "in-process control",
    ],
    "lab_data": [
        "out-of-specification", "oos", "oot", "out of trend", "laboratory",
        "analytical method", "method validation", "retest", "invalidate",
        "chromatographic", "hplc", "gc ", "system suitability",
    ],
    "equipment_qualification": [
        "equipment qualification", "iq ", "oq ", "pq ", "calibration",
        "preventive maintenance", "equipment maintenance", "instrument",
    ],
    "capa": [
        "corrective action", "preventive action", "capa", "investigation",
        "root cause", "effectiveness check", "deviation investigation",
    ],
    "training": [
        "training", "qualification of personnel", "competency", "gmp training",
        "personnel qualification",
    ],
    "environmental_monitoring": [
        "environmental monitoring", "em ", "bioburden", "endotoxin",
        "microbial", "contamination", "cleanroom", "air sampling",
    ],
    "sterility_assurance": [
        "sterility", "aseptic", "sterilization", "filtration", "media fill",
        "container closure", "depyrogenation",
    ],
    "documentation": [
        "documentation", "batch record", "master production", "logbook",
        "record keeping", "written procedure", "sop ", "standard operating",
    ],
    "supplier_qualification": [
        "supplier", "vendor", "contract manufacturer", "cmo ", "raw material",
        "component qualification", "audit supplier",
    ],
    "change_control": [
        "change control", "change management", "post-approval change",
        "prior approval supplement",
    ],
    "stability": [
        "stability", "shelf life", "expiry", "degradation", "accelerated study",
    ],
}

SUB_SECTOR_KEYWORDS = {
    "SS-D1": ["pharmaceutical manufacturing", "drug product", "finished pharmaceutical", "solid oral", "tablet", "capsule", "liquid"],
    "SS-D2": ["api ", "active pharmaceutical ingredient", "drug substance", "chemical synthesis"],
    "SS-D3": ["sterile", "injectable", "aseptic", "fill-finish", "ophthalmic", "parenteral"],
    "SS-D4": ["otc ", "over-the-counter", "consumer health"],
    "SS-B1": ["biologic", "biosimilar", "monoclonal antibody", "protein", "biopharmaceutical"],
    "SS-B2": ["gene therapy", "cell therapy", "atmp", "cgt "],
    "SS-MD1": ["medical device", "class ii", "class iii", "combination product"],
    "SS-DX1": ["in vitro diagnostic", "ivd ", "diagnostic"],
    "SS-VAC": ["vaccine", "immunological", "adjuvant"],
}

CFR_PATTERN = re.compile(
    r'(?:21\s+CFR\s+(?:Part\s+)?(?:§§?\s*)?[\d.]+(?:\([a-z0-9]+\))*'
    r'|21\s+U\.S\.C\.\s+\d+(?:\([a-z]\))?'
    r'|section\s+\d+\(\w\)\(\d+\)'
    r'|FD&C\s+Act\s+section\s+\d+)',
    re.IGNORECASE,
)


def extract_cfr_citations(text: str) -> list[str]:
    raw = CFR_PATTERN.findall(text)
    # Strip malformed trailing open-parens that appear when FDA redacts (b)(4) content
    cleaned = [c.rstrip('(').strip() for c in raw]
    return list(dict.fromkeys(c for c in cleaned if c))


def map_categories(text: str) -> list[str]:
    text_lower = text.lower()
    return [cat for cat, kws in CATEGORY_KEYWORDS.items() if any(kw in text_lower for kw in kws)]


def map_sub_sectors(text: str) -> list[str]:
    text_lower = text.lower()
    return [ss for ss, kws in SUB_SECTOR_KEYWORDS.items() if any(kw in text_lower for kw in kws)]


def severity_from_record_type(record_type: str, outcome: str = "") -> str:
    if record_type in ("consent_decree", "injunction", "seizure"):
        return "critical"
    if record_type == "warning_letter":
        return "high"
    if "recall" in record_type:
        if "class i" in outcome.lower():
            return "critical"
        if "class ii" in outcome.lower():
            return "high"
        return "medium"
    return "medium"


# ── openFDA client ────────────────────────────────────────────────────────────

OPENFDA_BASE = "https://api.fda.gov"

OPENFDA_ENDPOINTS = {
    "drug_enforcement": f"{OPENFDA_BASE}/drug/enforcement.json",
    "device_enforcement": f"{OPENFDA_BASE}/device/enforcement.json",
    "food_enforcement": f"{OPENFDA_BASE}/food/enforcement.json",
}


async def fetch_openfda(
    client: httpx.AsyncClient,
    endpoint: str,
    years_back: int,
    limit: int = 100,
) -> list[dict]:
    cutoff = (datetime.now() - timedelta(days=365 * years_back)).strftime("%Y%m%d")
    results = []
    skip = 0

    while True:
        # Use spaces not +: httpx URL-encodes + as %2B which breaks Lucene range syntax
        params = {
            "search": f'report_date:[{cutoff} TO 99991231]',
            "limit": limit,
            "skip": skip,
        }
        try:
            resp = await client.get(endpoint, params=params, timeout=30)
            if resp.status_code == 404:
                break  # No more results
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("results", [])
            if not batch:
                break
            results.extend(batch)
            log.info(f"  Fetched {len(results)} records from {endpoint.split('/')[-2]}")
            if len(batch) < limit:
                break
            skip += limit
            await asyncio.sleep(0.5)  # Rate limit courtesy
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                break
            log.warning(f"openFDA error at skip={skip}: {e}")
            break
        except Exception as e:
            log.warning(f"openFDA fetch error: {e}")
            break

    return results


def parse_openfda_record(raw: dict, source: str) -> dict:
    """Map a raw openFDA enforcement record to our schema."""
    company = raw.get("recalling_firm", raw.get("company_name", "Unknown"))
    product_desc = raw.get("product_description", raw.get("reason_for_recall", ""))
    reason = raw.get("reason_for_recall", raw.get("product_description", ""))
    full_text = f"{product_desc} {reason}"

    recall_class = raw.get("classification", "")
    status = raw.get("status", "")
    outcome_map = {"Completed": "resolved", "Ongoing": "ongoing", "Terminated": "terminated"}
    outcome = outcome_map.get(status, status.lower() or "unknown")

    record_type = "recall"
    ref_num = raw.get("recall_number", raw.get("event_id", generate_uuid()[:8]))

    issue_date = raw.get("report_date", raw.get("recall_initiation_date", ""))
    if issue_date and len(issue_date) == 8:
        try:
            issue_date = datetime.strptime(issue_date, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass

    return {
        "agency": "FDA",
        "record_type": record_type,
        "reference_number": ref_num,
        "issue_date": issue_date,
        "company_cited": company[:255] if company else "Unknown",
        "sub_sectors": map_sub_sectors(full_text),
        "observation_categories": map_categories(full_text),
        "cfr_citations": extract_cfr_citations(full_text),
        "title": (product_desc[:200] if product_desc else "Enforcement Action"),
        "summary": reason[:1000] if reason else "",
        "observations": [],
        "outcome": outcome,
        "pattern_tags": [],
        "severity_indicator": severity_from_record_type(record_type, recall_class),
        "trending": False,
        "trend_velocity": None,
    }


# ── FDA Warning Letters scraper ───────────────────────────────────────────────

WL_RSS_URLS = [
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/warning-letters/rss.xml",
]

WL_SEARCH_URL = "https://www.accessdata.fda.gov/scripts/warningletters/wldownloads.cfm"


async def fetch_warning_letters(
    client: httpx.AsyncClient, years_back: int
) -> list[dict]:
    records = []
    cutoff = datetime.now() - timedelta(days=365 * years_back)

    for rss_url in WL_RSS_URLS:
        try:
            resp = await client.get(rss_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml-xml")
            items = soup.find_all("item")
            log.info(f"  Found {len(items)} warning letter RSS items")

            for item in items:
                try:
                    pub_date_str = item.find("pubDate")
                    if pub_date_str:
                        from email.utils import parsedate_to_datetime
                        pub_date = parsedate_to_datetime(pub_date_str.text)
                        if pub_date.replace(tzinfo=None) < cutoff:
                            continue

                    title_tag = item.find("title")
                    link_tag = item.find("link")
                    desc_tag = item.find("description")

                    title = title_tag.text.strip() if title_tag else "Warning Letter"
                    link = link_tag.text.strip() if link_tag else ""
                    description = desc_tag.text.strip() if desc_tag else ""

                    # Try to get more detail from the letter page
                    observations, full_text = await _scrape_wl_page(client, link, description)

                    record = {
                        "agency": "FDA",
                        "record_type": "warning_letter",
                        "reference_number": link.split("/")[-1][:100] if link else generate_uuid()[:8],
                        "issue_date": pub_date_str.text[:10] if pub_date_str else "",
                        "company_cited": _extract_company_from_wl_title(title),
                        "sub_sectors": map_sub_sectors(full_text),
                        "observation_categories": map_categories(full_text),
                        "cfr_citations": extract_cfr_citations(full_text),
                        "title": title[:500],
                        "summary": description[:500],
                        "observations": observations[:10],
                        "outcome": "warning_letter_issued",
                        "pattern_tags": [],
                        "severity_indicator": "high",
                        "trending": False,
                        "trend_velocity": None,
                    }
                    records.append(record)
                    await asyncio.sleep(0.3)

                except Exception as e:
                    log.debug(f"Skipping WL item: {e}")
                    continue

        except Exception as e:
            log.warning(f"Warning letter RSS fetch failed ({rss_url}): {e}")

    # Also try the bulk download page for older letters
    try:
        bulk_records = await _fetch_wl_bulk(client, years_back)
        records.extend(bulk_records)
    except Exception as e:
        log.warning(f"WL bulk fetch failed: {e}")

    return records


async def _scrape_wl_page(
    client: httpx.AsyncClient, url: str, fallback: str
) -> tuple[list[str], str]:
    """Scrape a warning letter page for observations and full text."""
    if not url or not url.startswith("http"):
        return [], fallback
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        body = soup.get_text(separator=" ", strip=True)[:8000]

        # Extract numbered observations (common pattern in WLs)
        obs_patterns = re.findall(
            r'(?:^|\n)\s*(?:\d+[\.\)]\s+|•\s+|Observation\s+\d+[:\s])(.{50,400})',
            body, re.MULTILINE
        )
        return obs_patterns[:15], body
    except Exception:
        return [], fallback


async def _fetch_wl_bulk(
    client: httpx.AsyncClient, years_back: int
) -> list[dict]:
    """
    Fetch from FDA's downloadable warning letter database.
    FDA provides a tab-separated export at a known URL.
    """
    records = []
    cutoff_year = datetime.now().year - years_back

    # FDA's CFSAN warning letter data (food/drug)
    urls_to_try = [
        f"https://www.accessdata.fda.gov/scripts/warningletters/wlresults.cfm?year={yr}"
        for yr in range(cutoff_year, datetime.now().year + 1)
    ]

    for url in urls_to_try:
        page_url = url
        seen_on_page: set[str] = set()
        while page_url:
            try:
                resp = await client.get(page_url, timeout=20, follow_redirects=True)
                if resp.status_code != 200:
                    break
                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select("table tr")[1:]  # Skip header
                if not rows:
                    break
                page_count = 0
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) < 3:
                        continue
                    company = cols[0].get_text(strip=True)
                    subject = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    date_str = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    ref = f"WL-{date_str[:10]}-{company[:20]}".replace(" ", "-")
                    if ref in seen_on_page:
                        continue
                    seen_on_page.add(ref)
                    full_text = f"{company} {subject}"
                    records.append({
                        "agency": "FDA",
                        "record_type": "warning_letter",
                        "reference_number": ref[:100],
                        "issue_date": date_str[:10],
                        "company_cited": company[:255],
                        "sub_sectors": map_sub_sectors(full_text),
                        "observation_categories": map_categories(full_text),
                        "cfr_citations": extract_cfr_citations(full_text),
                        "title": subject[:500],
                        "summary": subject[:500],
                        "observations": [],
                        "outcome": "warning_letter_issued",
                        "pattern_tags": [],
                        "severity_indicator": "high",
                        "trending": False,
                        "trend_velocity": None,
                    })
                    page_count += 1
                log.debug(f"  WL bulk page {page_url}: {page_count} rows")

                # Follow pagination — look for a "Next" link
                next_link = soup.find("a", string=re.compile(r"next|>", re.I))
                if next_link and next_link.get("href"):
                    href = next_link["href"]
                    if href.startswith("http"):
                        page_url = href
                    else:
                        from urllib.parse import urljoin
                        page_url = urljoin(page_url, href)
                else:
                    page_url = None
                await asyncio.sleep(0.5)
            except Exception as e:
                log.debug(f"Bulk WL fetch skip ({page_url}): {e}")
                break

    return records


def _extract_company_from_wl_title(title: str) -> str:
    # WL titles often start with company name before " -" or " –"
    for sep in [" - ", " – ", ": ", " | "]:
        if sep in title:
            return title.split(sep)[0].strip()[:255]
    return title[:255]


# ── EMA non-compliance scraper ────────────────────────────────────────────────

EMA_NONCOMPLIANCE_URL = (
    "https://www.ema.europa.eu/en/human-regulatory-overview/compliance-and-monitoring/"
    "good-manufacturing-practice-gmp-compliance/gmp-non-compliance-reports"
)


async def fetch_ema_noncompliance(
    client: httpx.AsyncClient, years_back: int
) -> list[dict]:
    records = []
    cutoff = datetime.now() - timedelta(days=365 * years_back)

    try:
        resp = await client.get(EMA_NONCOMPLIANCE_URL, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # EMA lists non-compliance reports in a table
        rows = soup.select("table tbody tr")
        log.info(f"  Found {len(rows)} EMA non-compliance rows")

        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue

                company = cols[0].get_text(strip=True)
                deficiency = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                date_str = cols[-1].get_text(strip=True)

                full_text = f"{company} {deficiency}"

                records.append({
                    "agency": "EMA",
                    "record_type": "gmp_noncompliance",
                    "reference_number": f"EMA-NC-{generate_uuid()[:8]}",
                    "issue_date": date_str[:10],
                    "company_cited": company[:255],
                    "sub_sectors": map_sub_sectors(full_text),
                    "observation_categories": map_categories(full_text),
                    "cfr_citations": [],
                    "title": deficiency[:500] or "GMP Non-Compliance",
                    "summary": deficiency[:1000],
                    "observations": [],
                    "outcome": "gmp_noncompliance_statement",
                    "pattern_tags": [],
                    "severity_indicator": "high",
                    "trending": False,
                    "trend_velocity": None,
                })
            except Exception:
                continue

    except Exception as e:
        log.warning(f"EMA non-compliance fetch failed: {e}")

    return records


# ── Trend analysis ────────────────────────────────────────────────────────────

def compute_trends(records: list[dict]) -> list[dict]:
    """
    Mark records as trending if their observation_categories
    appear frequently in recent records (last 12 months).
    """
    from collections import Counter
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    recent_cats: list[str] = []
    for r in records:
        if r.get("issue_date", "") >= cutoff:
            recent_cats.extend(r.get("observation_categories", []))

    counts = Counter(recent_cats)
    # A category is "trending" if it appears in 5+ recent records
    trending_threshold = 5
    trending_cats = {cat for cat, cnt in counts.items() if cnt >= trending_threshold}
    total = len(records)

    for r in records:
        cats = set(r.get("observation_categories", []))
        if cats & trending_cats:
            r["trending"] = True
            # Velocity = fraction of recent records vs all records with this category
            for cat in cats & trending_cats:
                all_count = sum(1 for rec in records if cat in rec.get("observation_categories", []))
                r["trend_velocity"] = round(counts[cat] / max(all_count, 1), 3)
                break
    return records


# ── Database writer ───────────────────────────────────────────────────────────

async def write_to_db(records: list[dict], db_url: str, dry_run: bool = False) -> int:
    if dry_run:
        log.info(f"DRY RUN — would insert {len(records)} records")
        for r in records[:5]:
            print(f"  [{r['record_type']}] {r['company_cited']} — {r['title'][:80]}")
            print(f"    cats={r['observation_categories']} cfr={r['cfr_citations'][:2]}")
        return 0

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inserted = 0
    async with async_session() as session:
        for r in records:
            # Skip if reference_number already exists
            if r.get("reference_number"):
                existing = await session.execute(
                    select(EnforcementRecord).where(
                        EnforcementRecord.reference_number == r["reference_number"]
                    )
                )
                if existing.scalar_one_or_none():
                    continue

            record = EnforcementRecord(
                id=generate_uuid(),
                agency=r["agency"],
                record_type=r["record_type"],
                reference_number=r.get("reference_number"),
                issue_date=r.get("issue_date"),
                company_cited=r.get("company_cited"),
                sub_sectors=r.get("sub_sectors", []),
                observation_categories=r.get("observation_categories", []),
                cfr_citations=r.get("cfr_citations", []),
                title=r.get("title"),
                summary=r.get("summary"),
                observations=r.get("observations", []),
                outcome=r.get("outcome"),
                pattern_tags=r.get("pattern_tags", []),
                severity_indicator=r.get("severity_indicator", "medium"),
                trending=r.get("trending", False),
                trend_velocity=r.get("trend_velocity"),
            )
            session.add(record)
            inserted += 1

            if inserted % 100 == 0:
                await session.commit()
                log.info(f"  Committed {inserted} records so far…")

        await session.commit()

    await engine.dispose()
    return inserted


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Seed Clyira enforcement corpus from public sources")
    parser.add_argument("--years", type=int, default=3, help="Years of history to fetch (default: 3)")
    parser.add_argument("--source", choices=["all", "fda", "wl", "ema", "food"], default="all",
                        help="Data source: all, fda (openFDA drug+device), food (openFDA food), wl (warning letters), ema")
    parser.add_argument("--dry-run", action="store_true", help="Print records without inserting")
    parser.add_argument("--db", default=None, help="Override DATABASE_URL")
    args = parser.parse_args()

    # Resolve database URL
    db_url = args.db or os.environ.get("DATABASE_URL", "")
    if not db_url and not args.dry_run:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip('"')
    if not db_url and not args.dry_run:
        log.error("No DATABASE_URL found. Set env var or pass --db")
        sys.exit(1)

    log.info(f"Enforcement corpus seeder — source={args.source} years={args.years} dry_run={args.dry_run}")

    all_records: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:

        if args.source in ("all", "fda"):
            log.info("Fetching openFDA drug enforcement records…")
            raw_drug = await fetch_openfda(client, OPENFDA_ENDPOINTS["drug_enforcement"], args.years)
            drug_records = [parse_openfda_record(r, "drug") for r in raw_drug]
            log.info(f"  Parsed {len(drug_records)} drug enforcement records")
            all_records.extend(drug_records)

            log.info("Fetching openFDA device enforcement records…")
            raw_device = await fetch_openfda(client, OPENFDA_ENDPOINTS["device_enforcement"], args.years)
            device_records = [parse_openfda_record(r, "device") for r in raw_device]
            log.info(f"  Parsed {len(device_records)} device enforcement records")
            all_records.extend(device_records)

        if args.source in ("all", "food"):
            log.info("Fetching openFDA food enforcement records…")
            raw_food = await fetch_openfda(client, OPENFDA_ENDPOINTS["food_enforcement"], args.years)
            food_records = [parse_openfda_record(r, "food") for r in raw_food]
            log.info(f"  Parsed {len(food_records)} food enforcement records")
            all_records.extend(food_records)

        if args.source in ("all", "wl"):
            log.info("Fetching FDA Warning Letters…")
            wl_records = await fetch_warning_letters(client, args.years)
            log.info(f"  Parsed {len(wl_records)} warning letter records")
            all_records.extend(wl_records)

        if args.source in ("all", "ema"):
            log.info("Fetching EMA GMP non-compliance reports…")
            ema_records = await fetch_ema_noncompliance(client, args.years)
            log.info(f"  Parsed {len(ema_records)} EMA records")
            all_records.extend(ema_records)

    # Keep all records — even those without matched categories are useful for trend analysis
    log.info(f"Total records fetched: {len(all_records)}")

    # Compute trend analysis
    all_records = compute_trends(all_records)
    trending = sum(1 for r in all_records if r.get("trending"))
    log.info(f"Trending patterns identified: {trending} records")

    # Write to DB
    inserted = await write_to_db(all_records, db_url, dry_run=args.dry_run)
    if not args.dry_run:
        log.info(f"Done — inserted {inserted} new enforcement records into database")
    else:
        log.info(f"Dry run complete — {len(all_records)} records would be inserted")


if __name__ == "__main__":
    asyncio.run(main())
