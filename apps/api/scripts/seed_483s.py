"""
FDA Form 483 Seeder
===================
Fetches Form 483 inspection observation documents from the FDA's EFTS
full-text search system, downloads the PDFs, extracts numbered observations,
and writes rag_index/observations_483.jsonl.

Same schema as observations.jsonl with source_type="483" added.

Usage:
    cd apps/api
    python scripts/seed_483s.py
    python scripts/seed_483s.py --years 5 --dry-run
"""
import asyncio
import argparse
import io
import json
import logging
import re
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_483s")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "observations_483.jsonl"

EFTS_SEARCH = "https://efts.fda.gov/EFTS-WEB/search.action"
EFTS_BACKGROUND = "https://efts.fda.gov/EFTS-WEB/background.html"
FDA_FOIA_INDEX = "https://www.accessdata.fda.gov/scripts/fdatrack/view/track_project.cfm"
FDA_483_PAGE = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/fda-inspection-observations"

PAGE_SIZE = 25

# Regex to detect numbered observation paragraphs in 483 text
OBS_RE = re.compile(
    r'(?:^|\n)\s*(?:Observation\s+(?:No\.?\s*)?\d+[:\s]|(?:\d+)\.?\s+(?=\S{20}))'
    r'(.{50,2000}?)(?=\n\s*(?:Observation\s+(?:No\.?\s*)?\d+[:\s]|\d+\.?\s+\S|\Z))',
    re.DOTALL | re.MULTILINE,
)

CFR_PATTERN = re.compile(
    r'21\s+CFR\s+(?:§§?\s*)?[\d.]+(?:\([a-z0-9]+\))*',
    re.IGNORECASE,
)


def _extract_cfr(text: str) -> list[str]:
    raw = CFR_PATTERN.findall(text)
    cleaned = [c.rstrip("(").strip() for c in raw]
    return list(dict.fromkeys(c for c in cleaned if c))


def _parse_483_text(
    text: str,
    company: str,
    year: str,
    office: str,
    source_url: str,
    fei: str = "",
) -> list[dict]:
    """Extract individual observations from 483 full text."""
    records = []

    # Try structured observation extraction
    matches = OBS_RE.findall(text)
    if matches:
        for i, obs_text in enumerate(matches, 1):
            body = re.sub(r"\s+", " ", obs_text).strip()
            if len(body) < 30:
                continue
            rec_id = f"483-{fei or company[:20].replace(' ','-').lower()}-{year}-obs{i}"
            records.append({
                "id": rec_id,
                "text": body[:3000],
                "company": company[:255],
                "year": year,
                "office": office or "ORA",
                "source_url": source_url,
                "subject": "FDA Inspection",
                "cfr_citations": _extract_cfr(body),
                "observation_num": i,
                "source_type": "483",
                "fei_number": fei,
            })
    else:
        # Fallback: treat whole text as one observation block
        body = re.sub(r"\s+", " ", text[:3000]).strip()
        if len(body) > 50:
            rec_id = f"483-{fei or company[:20].replace(' ','-').lower()}-{year}-obs1"
            records.append({
                "id": rec_id,
                "text": body,
                "company": company[:255],
                "year": year,
                "office": office or "ORA",
                "source_url": source_url,
                "subject": "FDA Inspection",
                "cfr_citations": _extract_cfr(body),
                "observation_num": 1,
                "source_type": "483",
                "fei_number": fei,
            })

    return records


async def extract_pdf_text(client: httpx.AsyncClient, url: str) -> str:
    if not url:
        return ""
    try:
        resp = await client.get(url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        log.debug(f"PDF download failed ({url}): {e}")
        return ""

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        pass

    return ""


async def fetch_efts_page(
    client: httpx.AsyncClient,
    date_from: str,
    date_to: str,
    page_num: int,
) -> tuple[list[dict], int]:
    """Fetch one page of EFTS search results for Form 483 documents.
    Returns (results_list, total_count).
    """
    params = {
        "query": "483",
        "dateRangeField": "date",
        "dateFrom": date_from,
        "dateTo": date_to,
        "forms": "483",
        "pageSize": PAGE_SIZE,
        "pageNumber": page_num,
    }
    try:
        resp = await client.get(EFTS_SEARCH, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data.get("hits", {}).get("hits", []))
        total = data.get("totalMatchCount", data.get("hits", {}).get("total", {}).get("value", 0))
        if isinstance(total, dict):
            total = total.get("value", 0)
        return results, int(total)
    except Exception as e:
        log.warning(f"EFTS page {page_num} failed: {e}")
        return [], 0


def _parse_efts_result(result: dict) -> tuple[str, str, str, str, str]:
    """Extract (company, year, office, source_url, fei) from an EFTS result."""
    src = result.get("_source", result)
    company = (
        src.get("firm", src.get("company", src.get("firmName", "")))
    )
    date_str = src.get("date", src.get("issueDate", ""))
    year = date_str[:4] if date_str else str(datetime.now().year)
    office = src.get("office", src.get("district", "ORA"))

    # PDF URL
    pdf_url = ""
    for key in ("pdfUrl", "pdf_url", "document_url", "url", "fileUrl"):
        if src.get(key):
            pdf_url = src[key]
            break

    fei = str(src.get("fei", src.get("feiNumber", "")))
    return str(company)[:255], str(year)[:4], str(office)[:100], pdf_url, fei


async def scrape_fda_483_page(
    client: httpx.AsyncClient, years_back: int
) -> list[tuple[str, str, str, str, str]]:
    """
    Fallback: scrape the FDA inspection observations HTML page for 483 links.
    Returns list of (company, year, office, pdf_url, fei).
    """
    results = []
    cutoff_year = datetime.now().year - years_back
    page_url: Optional[str] = FDA_483_PAGE

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.warning(f"FDA 483 page scrape failed ({page_url}): {e}")
            break

        rows = soup.select("table tbody tr, .views-row, article")
        for row in rows:
            try:
                cells = row.find_all("td")
                company = cells[0].get_text(strip=True) if cells else row.get_text(" ", strip=True)[:100]
                date_str = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                year = date_str[:4] if date_str else ""
                if year and int(year) < cutoff_year:
                    continue
                pdf_link = row.find("a", href=re.compile(r"\.pdf", re.I))
                if pdf_link:
                    href = pdf_link["href"]
                    pdf_url = href if href.startswith("http") else urljoin("https://www.fda.gov", href)
                    results.append((company, year or str(datetime.now().year), "ORA", pdf_url, ""))
            except Exception:
                continue

        next_link = soup.find("a", rel="next") or soup.find("li", class_="pager__item--next")
        if next_link:
            a = next_link if next_link.name == "a" else next_link.find("a")
            if a and a.get("href"):
                href = a["href"]
                page_url = href if href.startswith("http") else urljoin(FDA_483_PAGE, href)
            else:
                page_url = None
        else:
            page_url = None
        await asyncio.sleep(0.35)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed FDA Form 483 observations")
    parser.add_argument("--years", type=int, default=5, help="Years of history (default 5)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(days=365 * args.years)
    date_from = cutoff.strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")

    log.info(f"FDA 483 seeder — from={date_from} to={date_to} dry_run={args.dry_run}")

    # Load existing IDs to skip
    existing_ids: set[str] = set()
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    log.info(f"  {len(existing_ids)} existing records to skip")

    all_records: list[dict] = []
    seen_ids = set(existing_ids)

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:

        # Primary: EFTS paginated search
        log.info("Fetching FDA 483s via EFTS search…")
        page_num = 1
        total = None

        while True:
            results, total_count = await fetch_efts_page(client, date_from, date_to, page_num)
            if total is None:
                total = total_count
                log.info(f"  EFTS reports {total} total 483 documents")

            if not results:
                break

            for result in results:
                try:
                    company, year, office, pdf_url, fei = _parse_efts_result(result)
                    if not pdf_url:
                        continue
                    log.debug(f"  Downloading {company} ({year}) {pdf_url}")
                    text = await extract_pdf_text(client, pdf_url)
                    if not text.strip():
                        await asyncio.sleep(0.3)
                        continue
                    records = _parse_483_text(text, company, year, office, pdf_url, fei)
                    new = [r for r in records if r["id"] not in seen_ids]
                    for r in new:
                        seen_ids.add(r["id"])
                    all_records.extend(new)
                    await asyncio.sleep(0.4)
                except Exception as e:
                    log.debug(f"  Record parse error: {e}")
                    continue

            log.info(f"  EFTS page {page_num}: {len(results)} results — running total {len(all_records)} observations")

            if len(results) < PAGE_SIZE:
                break
            if total and page_num * PAGE_SIZE >= total:
                break
            page_num += 1
            await asyncio.sleep(0.35)

        # Fallback: scrape FDA 483 observations page
        if len(all_records) == 0:
            log.info("EFTS returned no results — falling back to FDA observations page scrape")
            fallback_items = await scrape_fda_483_page(client, args.years)
            log.info(f"  Found {len(fallback_items)} items via page scrape")
            for company, year, office, pdf_url, fei in fallback_items:
                try:
                    text = await extract_pdf_text(client, pdf_url)
                    if not text.strip():
                        await asyncio.sleep(0.3)
                        continue
                    records = _parse_483_text(text, company, year, office, pdf_url, fei)
                    new = [r for r in records if r["id"] not in seen_ids]
                    for r in new:
                        seen_ids.add(r["id"])
                    all_records.extend(new)
                    await asyncio.sleep(0.4)
                except Exception as e:
                    log.debug(f"  Fallback record error: {e}")

    log.info(f"Total new 483 observations: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['company']} {r['year']}] obs{r['observation_num']}: {r['text'][:80]}")
        log.info("Dry run — no file written")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if existing_ids else "w"
    with open(OUTPUT_PATH, mode, encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"{'Appended' if existing_ids else 'Written'} {len(all_records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
