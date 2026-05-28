"""
E2: WHO Notices of Concern/Suspension/Delisting Seeder
========================================================
Scrapes WHO Notices of Concern and related suspension/delisting notices
from the WHO Prequalification website.
Output: rag_index/who_notices.jsonl

Usage:
    python seed_who_notices.py
    python seed_who_notices.py --dry-run
"""
import argparse
import json
import logging
import re
import sys
import os
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FILE = "who_notices.jsonl"

WHO_NOTICE_URLS = [
    "https://extranet.who.int/prequal/inspection-services/notice-concern",
    "https://extranet.who.int/prequal/content/notices-concern",
    "https://extranet.who.int/prequal/inspection_services/notice_concern",
    (
        "https://www.who.int/teams/health-product-policy-and-standards/standards-and-specifications/"
        "prequalification-of-medical-products-(IVDs,-medicines,-vaccines-and-immunization-devices-and-vector-control)/"
        "inspection-services"
    ),
    "https://extranet.who.int/prequal/content/noc",
]

WHO_SUSPENSION_URLS = [
    "https://extranet.who.int/prequal/inspection-services/suspension-delisting",
    "https://extranet.who.int/prequal/content/suspension-delisting",
]

WHO_BASE = "https://extranet.who.int"
WHO_MAIN_BASE = "https://www.who.int"


def parse_notice_type(text: str) -> str:
    t = text.lower()
    if "delist" in t:
        return "Delisting"
    if "suspension" in t or "suspend" in t:
        return "Suspension"
    if "concern" in t:
        return "Notice of Concern"
    if "withdraw" in t:
        return "Withdrawal"
    if "voluntary" in t:
        return "Voluntary Withdrawal"
    return "Notice"


def parse_notices_from_page(soup: BeautifulSoup, base_url: str, notice_type_hint: str = "") -> list[dict]:
    """Parse notices from a WHO Prequal page."""
    records = []

    # Tables
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        log.debug(f"  Table headers: {headers[:8]}")

        col = {}
        for i, h in enumerate(headers):
            if "manufacturer" in h or "company" in h or "site" in h or "applicant" in h:
                col.setdefault("manufacturer", i)
            elif "country" in h:
                col.setdefault("country", i)
            elif "product" in h or "medicine" in h or "inn" in h:
                col.setdefault("product", i)
            elif "type" in h or "notice" in h:
                col.setdefault("notice_type", i)
            elif "reason" in h or "ground" in h or "comment" in h:
                col.setdefault("reason", i)
            elif "date" in h:
                col.setdefault("date", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key, fallback_idx=None):
                    idx = col.get(key, fallback_idx)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                manufacturer = cell("manufacturer", 0)
                country = cell("country", 1)
                product = cell("product", 2)
                notice_type = cell("notice_type") or notice_type_hint
                reason_text = cell("reason")
                date = cell("date")

                if not manufacturer and not product:
                    continue

                if not notice_type:
                    notice_type = parse_notice_type(row.get_text())

                link = row.find("a", href=True)
                row_url = urljoin(base_url, link["href"]) if link else base_url

                text = (
                    f"WHO {notice_type}. Manufacturer: {manufacturer}. "
                    f"Country: {country}. Product: {product}. "
                    f"Date: {date}. Reason: {reason_text}."
                )

                records.append({
                    "id": make_id("WHO-NOTICE", manufacturer, notice_type, date),
                    "source_id": "WHO-NOTICE",
                    "source_agency": "WHO",
                    "source_type": "notice_of_concern",
                    "manufacturer": manufacturer,
                    "country": country,
                    "product": product,
                    "notice_type": notice_type,
                    "reason_text": reason_text,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Notice row error: {e}")
                continue

    if not records:
        # List item fallback
        for item in soup.select(
            "article, .views-row, .node--type-notice, "
            ".field-items > .field-item, li"
        ):
            try:
                title_el = item.find(["h3", "h2", "h4"])
                if not title_el:
                    continue
                manufacturer = title_el.get_text(strip=True)
                if len(manufacturer) < 3:
                    continue

                link = item.find("a", href=True)
                item_url = urljoin(base_url, link["href"]) if link else base_url

                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
                date = date_el.get_text(strip=True) if date_el else ""

                desc_el = item.find("p")
                desc = desc_el.get_text(strip=True) if desc_el else ""

                notice_type = notice_type_hint or parse_notice_type(item.get_text())

                text = f"WHO {notice_type}. {manufacturer}. {desc}. Date: {date}."
                records.append({
                    "id": make_id("WHO-NOTICE", manufacturer, notice_type, date),
                    "source_id": "WHO-NOTICE",
                    "source_agency": "WHO",
                    "source_type": "notice_of_concern",
                    "manufacturer": manufacturer,
                    "country": "",
                    "product": "",
                    "notice_type": notice_type,
                    "reason_text": desc,
                    "date": date,
                    "text": text,
                    "source_url": item_url,
                })
            except Exception as e:
                log.debug(f"Notice item error: {e}")
                continue

    return records


def scrape_url_list(urls: list[str], notice_type_hint: str = "") -> list[dict]:
    """Try a list of URLs, paginating each, return first successful batch."""
    all_records = []

    for base_url in urls:
        log.info(f"Trying WHO notice URL: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            log.info(f"  No response from {base_url}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        records = parse_notices_from_page(soup, base_url, notice_type_hint)

        if records:
            log.info(f"  Page 1: {len(records)} records")
            all_records.extend(records)

            # Paginate
            page = 2
            while True:
                paginated = f"{base_url}?page={page}"
                resp2 = get(paginated, delay=1.5, timeout=30.0)
                if not resp2:
                    break
                soup2 = BeautifulSoup(resp2.text, "lxml")
                more = parse_notices_from_page(soup2, paginated, notice_type_hint)
                if not more:
                    break
                all_records.extend(more)
                log.info(f"  Page {page}: {len(more)} records")
                page += 1

            break
        else:
            log.info(f"  No records at {base_url}")
            time.sleep(1.5)

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed WHO Notices of Concern into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["manufacturer", "notice_type", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    log.info("Scraping WHO Notices of Concern…")
    concern_records = scrape_url_list(WHO_NOTICE_URLS, "Notice of Concern")
    log.info(f"  Notices of Concern: {len(concern_records)}")
    all_records.extend(concern_records)

    log.info("Scraping WHO Suspension/Delisting notices…")
    suspension_records = scrape_url_list(WHO_SUSPENSION_URLS, "Suspension")
    log.info(f"  Suspension/Delisting: {len(suspension_records)}")
    all_records.extend(suspension_records)

    new_records = []
    for r in all_records:
        key = (r.get("manufacturer", ""), r.get("notice_type", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
