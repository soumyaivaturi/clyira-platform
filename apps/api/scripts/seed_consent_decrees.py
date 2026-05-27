"""
FDA Consent Decrees Seeder
==========================
Scrapes the FDA consent decrees index page and individual decree pages to
extract company, date, terms summary, and product area, writing
rag_index/consent_decrees.jsonl.

Usage:
    cd apps/api
    python scripts/seed_consent_decrees.py
    python scripts/seed_consent_decrees.py --dry-run
"""
import asyncio
import argparse
import json
import logging
import re
import sys
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_consent_decrees")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "consent_decrees.jsonl"

FDA_CD_INDEX = (
    "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/"
    "compliance-actions-and-activities/consent-decrees-permanent-injunctions"
)
FDA_BASE = "https://www.fda.gov"

PRODUCT_AREA_KEYWORDS = {
    "drugs": ["drug", "pharmaceutical", "cgmp", "211", "210"],
    "devices": ["device", "qsr", "820", "mdufma"],
    "biologics": ["biologic", "blood", "vaccine", "plasma"],
    "food": ["food", "dietary supplement", "cfsan"],
    "veterinary": ["veterinary", "animal"],
}


def _infer_product_area(text: str) -> str:
    tl = text.lower()
    for area, kws in PRODUCT_AREA_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            return area
    return "general"


def _natural_key(company: str, date: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", company[:30].lower()).strip("-")
    return f"cd-{slug}-{date[:10].replace('-', '')}"


async def fetch_detail_page(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """Fetch a consent decree detail page and return (terms_summary, date)."""
    try:
        resp = await client.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove nav/header/footer noise
        for tag in soup.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        body_text = soup.get_text(" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text)

        # Extract date from page text
        date_match = re.search(
            r'(?:filed|entered|issued|signed|dated)[:\s]+(\w+\s+\d{1,2},\s*\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            body_text, re.IGNORECASE
        )
        date_str = ""
        if date_match:
            raw = date_match.group(1).strip()
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
                try:
                    from datetime import datetime
                    date_str = datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    pass

        return body_text[:2000], date_str
    except Exception as e:
        log.debug(f"Detail page fetch failed ({url}): {e}")
        return "", ""


async def scrape_index(client: httpx.AsyncClient) -> list[tuple[str, str, str]]:
    """
    Scrape the FDA consent decrees index page and all pagination.
    Returns list of (company, date, detail_url).
    """
    results: list[tuple[str, str, str]] = []
    page_url: Optional[str] = FDA_CD_INDEX

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.warning(f"Index page fetch failed ({page_url}): {e}")
            break

        # FDA consent decree pages use tables or lists of entries
        # Pattern 1: table rows with company/date/link
        rows = soup.select("table tbody tr")
        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                company = cols[0].get_text(strip=True)
                date_str = ""
                detail_url = ""
                # Find date in any column
                for c in cols:
                    text = c.get_text(strip=True)
                    if re.match(r"\d{1,2}/\d{1,2}/\d{4}|\w+ \d{4}", text):
                        date_str = text
                    link = c.find("a")
                    if link and link.get("href"):
                        href = link["href"]
                        detail_url = href if href.startswith("http") else urljoin(FDA_BASE, href)
                if company:
                    results.append((company[:255], date_str[:20], detail_url))
            except Exception:
                continue

        # Pattern 2: unordered list items with links
        for li in soup.select("ul.list-unstyled li, .field-item li"):
            try:
                a = li.find("a")
                if not a:
                    continue
                company = a.get_text(strip=True)
                href = a["href"]
                detail_url = href if href.startswith("http") else urljoin(FDA_BASE, href)
                # Try to extract date from surrounding text
                text = li.get_text(" ", strip=True)
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4}|\w+\s+\d{1,2},\s*\d{4})', text)
                date_str = date_match.group(1) if date_match else ""
                if company and detail_url:
                    results.append((company[:255], date_str[:20], detail_url))
            except Exception:
                continue

        # Follow pagination
        next_link = soup.find("a", rel="next") or soup.find(
            "li", class_=re.compile(r"pager.*next|next.*pager")
        )
        page_url = None
        if next_link:
            a = next_link if next_link.name == "a" else next_link.find("a")
            if a and a.get("href"):
                href = a["href"]
                page_url = href if href.startswith("http") else urljoin(FDA_CD_INDEX, href)

        await asyncio.sleep(0.35)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed FDA consent decree records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info(f"Consent decrees seeder — dry_run={args.dry_run}")

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

        log.info("Scraping FDA consent decrees index…")
        entries = await scrape_index(client)
        log.info(f"  Found {len(entries)} index entries")

        for company, date_str, detail_url in entries:
            try:
                terms_summary = ""
                page_date = date_str

                if detail_url:
                    terms_summary, page_date = await fetch_detail_page(client, detail_url)
                    await asyncio.sleep(0.35)

                date = page_date or date_str
                rec_id = _natural_key(company, date)
                if rec_id in seen_ids:
                    continue
                seen_ids.add(rec_id)

                product_area = _infer_product_area(f"{company} {terms_summary}")

                all_records.append({
                    "id": rec_id,
                    "company": company[:255],
                    "date": date[:20],
                    "terms_summary": terms_summary[:2000],
                    "product_area": product_area,
                    "source_url": detail_url or FDA_CD_INDEX,
                    "source_type": "consent_decree",
                    "agency": "FDA",
                })
            except Exception as e:
                log.debug(f"Entry error ({company}): {e}")
                continue

    log.info(f"Total new consent decree records: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  {r['company']} ({r['date']}) — {r['product_area']}")
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
