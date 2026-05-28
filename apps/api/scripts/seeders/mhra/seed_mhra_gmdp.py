"""
B2: MHRA GMDP Non-Compliance Seeder
=====================================
Scrapes MHRA-GMDP database non-compliance statements from the public GMDP portal.
Output: rag_index/mhra_gmdp.jsonl

Usage:
    python seed_mhra_gmdp.py
    python seed_mhra_gmdp.py --dry-run
"""
import argparse
import json
import logging
import re
import sys
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlencode

import httpx
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FILE = "mhra_gmdp.jsonl"

# MHRA GMDP portal URLs
GMDP_PUBLIC_BASE = "https://gmdpipublic.mhra.gov.uk"
GMDP_NONCOMPLIANCE_URL = "https://gmdpipublic.mhra.gov.uk/NonCompliance"
GMDP_SEARCH_URL = "https://gmdpipublic.mhra.gov.uk/GmdpLicence/Search"
MHRA_CMS_URL = "https://cms.mhra.gov.uk/mhra"
MHRA_NONCOMPLIANCE_PAGE = (
    "https://www.gov.uk/government/collections/"
    "gmp-and-gdp-non-compliance-reports-from-eu-member-states"
)


def scrape_gmdp_noncompliance_portal() -> list[dict]:
    """Scrape the MHRA GMDP public portal for non-compliance statements."""
    records = []

    urls_to_try = [
        GMDP_NONCOMPLIANCE_URL,
        f"{GMDP_PUBLIC_BASE}/noncompliance",
        f"{GMDP_PUBLIC_BASE}/non-compliance",
        MHRA_NONCOMPLIANCE_PAGE,
    ]

    for base_url in urls_to_try:
        log.info(f"Trying GMDP non-compliance URL: {base_url}")
        resp = get(base_url, delay=1.0, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Try to find a table of non-compliance records
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
            log.info(f"  Found table with headers: {headers[:6]}")

            for row in rows[1:]:
                try:
                    cols = row.find_all("td")
                    if len(cols) < 2:
                        continue

                    # Try to map columns flexibly
                    def col_text(i):
                        return cols[i].get_text(strip=True) if i < len(cols) else ""

                    # Detect link in row for source_url
                    link_tag = row.find("a", href=True)
                    row_url = urljoin(base_url, link_tag["href"]) if link_tag else base_url

                    # Heuristic column mapping
                    site_name = col_text(0)
                    country = col_text(1) if len(cols) > 1 else ""
                    auth_type = col_text(2) if len(cols) > 2 else ""
                    status = col_text(3) if len(cols) > 3 else ""
                    date = col_text(4) if len(cols) > 4 else ""

                    if not site_name:
                        continue

                    text = (
                        f"MHRA GMDP Non-Compliance. Site: {site_name}. "
                        f"Country: {country}. Authorization type: {auth_type}. "
                        f"Status: {status}. Date: {date}."
                    )

                    records.append({
                        "id": make_id("MHRA-GMDP", site_name, date),
                        "source_id": "MHRA-GMDP",
                        "source_agency": "MHRA",
                        "source_type": "gmdp_record",
                        "site_name": site_name,
                        "country": country,
                        "authorization_type": auth_type,
                        "status": status,
                        "date": date,
                        "text": text,
                        "source_url": row_url,
                    })
                except Exception as e:
                    log.debug(f"Skipping row: {e}")
                    continue

        # Also try list items / definition lists (GOV.UK style)
        items = soup.select("article, .gem-c-document-list__item, li.gem-c-document-list__item")
        for item in items:
            try:
                title_el = item.find(["h3", "h2", "a"])
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    a = title_el.find("a", href=True) if title_el.name != "a" else None
                    link = a["href"] if a else ""

                row_url = urljoin(base_url, link) if link else base_url
                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
                date = date_el.get_text(strip=True) if date_el else ""
                desc_el = item.find("p")
                desc = desc_el.get_text(strip=True) if desc_el else ""

                if not title:
                    continue

                text = f"MHRA GMDP Record. {title}. {desc}. Date: {date}."
                records.append({
                    "id": make_id("MHRA-GMDP", title, date),
                    "source_id": "MHRA-GMDP",
                    "source_agency": "MHRA",
                    "source_type": "gmdp_record",
                    "site_name": title,
                    "country": "",
                    "authorization_type": "",
                    "status": "",
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Skipping item: {e}")
                continue

        if records:
            log.info(f"  Extracted {len(records)} records from {base_url}")
            break
        else:
            log.info(f"  No structured data found at {base_url}")
            time.sleep(1.0)

    return records


def scrape_gmdp_search_results() -> list[dict]:
    """Try the GMDP licence search to find non-compliant sites."""
    records = []
    search_urls = [
        f"{GMDP_PUBLIC_BASE}/GmdpLicence/Search?noncompliant=true",
        f"{GMDP_PUBLIC_BASE}/GmdpLicence?status=NonCompliant",
        f"{GMDP_PUBLIC_BASE}/site/search?status=non-compliant",
    ]

    for url in search_urls:
        resp = get(url, delay=1.0, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")
        if not rows:
            continue

        for row in rows:
            try:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue
                site_name = cols[0].get_text(strip=True)
                country = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                status = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                date = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                link = row.find("a", href=True)
                row_url = urljoin(url, link["href"]) if link else url

                text = f"MHRA GMDP Non-Compliant Site: {site_name}. Country: {country}. Status: {status}. Date: {date}."
                records.append({
                    "id": make_id("MHRA-GMDP", site_name, date),
                    "source_id": "MHRA-GMDP",
                    "source_agency": "MHRA",
                    "source_type": "gmdp_record",
                    "site_name": site_name,
                    "country": country,
                    "authorization_type": "",
                    "status": status,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Skipping search row: {e}")
                continue

        if records:
            log.info(f"  Found {len(records)} non-compliant sites from search")
            break

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed MHRA GMDP non-compliance records into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["site_name", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    log.info("Scraping MHRA GMDP non-compliance portal…")
    portal_records = scrape_gmdp_noncompliance_portal()
    log.info(f"  Portal records: {len(portal_records)}")
    all_records.extend(portal_records)

    if not all_records:
        log.info("Trying GMDP search…")
        search_records = scrape_gmdp_search_results()
        log.info(f"  Search records: {len(search_records)}")
        all_records.extend(search_records)

    new_records = []
    for r in all_records:
        key = (r.get("site_name", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
