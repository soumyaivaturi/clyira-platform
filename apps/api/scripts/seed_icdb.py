"""
FDA Inspection Classification Database (ICDB) Seeder
=====================================================
Scrapes the FDA ICDB search at accessdata.fda.gov/scripts/inspsearch/ to get
all NAI/VAI/OAI classified inspection records and writes
rag_index/inspections.jsonl.

Usage:
    cd apps/api
    python scripts/seed_icdb.py
    python scripts/seed_icdb.py --years 5 --dry-run
    python scripts/seed_icdb.py --classification OAI
"""
import asyncio
import argparse
import json
import logging
import re
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_icdb")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "inspections.jsonl"

ICDB_SEARCH_URL = "https://www.accessdata.fda.gov/scripts/inspsearch/inspsearch.cfm"
ICDB_BASE = "https://www.accessdata.fda.gov"

PAGE_SIZE = 25  # FDA ICDB returns 25 rows per page by default

# Classifications to fetch — all three
CLASSIFICATIONS = ["NAI", "VAI", "OAI"]


def _row_to_record(cols: list, detail_url: str = "") -> Optional[dict]:
    """Parse a table row from ICDB search results into a record dict."""
    if len(cols) < 6:
        return None
    texts = [c.get_text(" ", strip=True) for c in cols]

    firm_name = texts[0] if len(texts) > 0 else ""
    fei = re.sub(r"\s+", "", texts[1]) if len(texts) > 1 else ""
    city = texts[2] if len(texts) > 2 else ""
    state = texts[3] if len(texts) > 3 else ""
    country = texts[4] if len(texts) > 4 else ""

    # Date column — try to normalize
    date_raw = texts[5] if len(texts) > 5 else ""
    insp_date = ""
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            insp_date = datetime.strptime(date_raw.strip(), fmt).strftime("%Y-%m-%d")
            break
        except ValueError:
            pass

    classification = texts[6] if len(texts) > 6 else ""
    program_area = texts[7] if len(texts) > 7 else ""
    project_area = texts[8] if len(texts) > 8 else ""

    if not firm_name and not fei:
        return None

    natural_key = f"{fei}-{insp_date}" if fei and insp_date else f"{firm_name[:30]}-{insp_date}"
    return {
        "id": f"icdb-{re.sub(r'[^a-z0-9]+', '-', natural_key.lower()).strip('-')}",
        "firm_name": firm_name[:255],
        "fei_number": fei[:20],
        "city": city[:100],
        "state": state[:10],
        "country": country[:100],
        "inspection_date": insp_date,
        "classification": classification[:10].upper(),
        "program_area": program_area[:100],
        "project_area": project_area[:100],
        "detail_url": detail_url,
    }


async def search_icdb_page(
    client: httpx.AsyncClient,
    date_from: str,
    date_to: str,
    classification: str,
    page: int,
) -> tuple[list[dict], bool]:
    """
    POST a search to the ICDB and return (records, has_more).
    ICDB uses start_row for pagination (1-based).
    """
    start_row = (page - 1) * PAGE_SIZE + 1
    form_data = {
        "action": "Search",
        "FEI": "",
        "Company_Name": "",
        "City": "",
        "State_Code": "",
        "Country_Code": "",
        "Inspection_Start_Date": date_from,
        "Inspection_End_Date": date_to,
        "Class": classification,
        "program_area": "",
        "project_area_code": "",
        "startrow": str(start_row),
        "Submit": "Search",
    }
    try:
        resp = await client.post(
            ICDB_SEARCH_URL,
            data=form_data,
            timeout=30,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.warning(f"ICDB page {page} ({classification}) failed: {e}")
        return [], False

    # Parse the results table
    table = soup.find("table", id=re.compile(r"result", re.I)) or soup.find("table")
    if not table:
        return [], False

    rows = table.find_all("tr")[1:]  # skip header
    if not rows:
        return [], False

    records = []
    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue
        # Try to get a detail link
        detail_link = row.find("a", href=re.compile(r"inspsearch", re.I))
        detail_url = ""
        if detail_link and detail_link.get("href"):
            href = detail_link["href"]
            detail_url = href if href.startswith("http") else urljoin(ICDB_BASE, href)
        rec = _row_to_record(cols, detail_url)
        if rec:
            records.append(rec)

    # Check for a "Next" navigation or if we got a full page
    has_more = len(records) >= PAGE_SIZE
    next_link = soup.find("a", string=re.compile(r"next|>", re.I))
    if next_link:
        has_more = True

    return records, has_more


async def main():
    parser = argparse.ArgumentParser(description="Seed FDA ICDB inspection records")
    parser.add_argument("--years", type=int, default=10, help="Years of history (default 10)")
    parser.add_argument("--classification", default="", help="NAI, VAI, or OAI — default all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.now() - timedelta(days=365 * args.years)
    date_from = cutoff.strftime("%m/%d/%Y")
    date_to = datetime.now().strftime("%m/%d/%Y")

    classifications = (
        [args.classification.upper()] if args.classification
        else CLASSIFICATIONS
    )

    log.info(f"ICDB seeder — from={date_from} classes={classifications} dry_run={args.dry_run}")

    # Load existing IDs to dedup
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

        for cls in classifications:
            log.info(f"Fetching {cls} inspections…")
            page = 1
            cls_total = 0

            while True:
                records, has_more = await search_icdb_page(
                    client, date_from, date_to, cls, page
                )
                if not records:
                    break

                new = [r for r in records if r["id"] not in seen_ids]
                for r in new:
                    seen_ids.add(r["id"])
                all_records.extend(new)
                cls_total += len(new)

                log.info(f"  {cls} page {page}: {len(records)} rows, {len(new)} new")

                if not has_more:
                    break
                page += 1
                await asyncio.sleep(0.35)

            log.info(f"  {cls} total new: {cls_total}")

    log.info(f"Total new ICDB records: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['classification']}] {r['firm_name']} — {r['inspection_date']}")
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
