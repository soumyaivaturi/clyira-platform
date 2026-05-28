"""
E1: WHO Public Inspection Reports (WHOPIRs) Seeder
====================================================
Scrapes WHO Public Inspection Reports from the WHO Prequalification website.
Output: rag_index/who_whopirs.jsonl

Usage:
    python seed_who_whopirs.py
    python seed_who_whopirs.py --dry-run
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

OUTPUT_FILE = "who_whopirs.jsonl"

WHO_WHOPIR_PAGES = [
    "https://extranet.who.int/prequal/inspection-services/prequalification-reports/whopirs-medicines",
    "https://extranet.who.int/prequal/inspection-services/prequalification-reports/whopirs",
    "https://extranet.who.int/prequal/inspection_services/prequalification_reports/whopirs",
    "https://www.who.int/teams/health-product-policy-and-standards/standards-and-specifications/prequalification-of-medical-products-(IVDs,-medicines,-vaccines-and-immunization-devices-and-vector-control)/inspection-services",
    "https://extranet.who.int/prequal/content/inspection-reports",
]

WHO_PDF_BASE = "https://extranet.who.int/prequal/sites/default/files/documents/"
WHO_BASE = "https://extranet.who.int"


def parse_whopir_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract WHOPIR records from a page."""
    records = []

    # Try tables first
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        log.debug(f"  Table headers: {headers[:8]}")

        col = {}
        for i, h in enumerate(headers):
            if "manufacturer" in h or "company" in h or "site" in h:
                col.setdefault("manufacturer", i)
            elif "country" in h:
                col.setdefault("country", i)
            elif "date" in h and "inspection" in h:
                col.setdefault("inspection_date", i)
            elif "date" in h:
                col.setdefault("date", i)
            elif "outcome" in h or "result" in h or "status" in h:
                col.setdefault("outcome", i)
            elif "product" in h or "medicine" in h:
                col.setdefault("product", i)
            elif "report" in h or "whopir" in h:
                col.setdefault("report", i)

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
                inspection_date = cell("inspection_date") or cell("date", 2)
                outcome = cell("outcome", 3)

                if not manufacturer:
                    continue

                # Look for PDF link
                link = row.find("a", href=True)
                pdf_url = ""
                if link and link["href"].endswith(".pdf"):
                    pdf_url = urljoin(WHO_BASE, link["href"])
                elif link:
                    pdf_url = urljoin(base_url, link["href"])

                # Try to extract text from PDF
                report_text = ""
                if pdf_url and pdf_url.endswith(".pdf"):
                    log.debug(f"    Fetching WHOPIR PDF: {pdf_url}")
                    time.sleep(1.5)
                    pdf_resp = get(pdf_url, delay=1.5, timeout=60.0)
                    if pdf_resp and len(pdf_resp.content) > 1000:
                        report_text = pdf_to_text(pdf_resp.content, max_pages=30)
                        report_text = report_text[:5000]

                text = (
                    f"WHO Public Inspection Report (WHOPIR). "
                    f"Manufacturer: {manufacturer}. Country: {country}. "
                    f"Inspection date: {inspection_date}. Outcome: {outcome}. "
                    + (f"Report excerpt: {report_text[:500]}" if report_text else "")
                )

                records.append({
                    "id": make_id("WHO-WHOPIR", manufacturer, inspection_date),
                    "source_id": "WHO-WHOPIR",
                    "source_agency": "WHO",
                    "source_type": "public_inspection_report",
                    "manufacturer": manufacturer,
                    "country": country,
                    "inspection_date": inspection_date,
                    "outcome": outcome,
                    "text": text,
                    "date": inspection_date,
                    "source_url": pdf_url or base_url,
                })
            except Exception as e:
                log.debug(f"WHOPIR table row error: {e}")
                continue

    if not records:
        # Fallback: list items
        for item in soup.select(
            "article, .views-row, .field-items > .field-item, "
            ".node, li.whopir-item"
        ):
            try:
                title_el = item.find(["h3", "h2", "h4"])
                if not title_el:
                    continue
                manufacturer = title_el.get_text(strip=True)

                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date", re.I)})
                inspection_date = date_el.get_text(strip=True) if date_el else ""

                link = item.find("a", href=True)
                item_url = urljoin(base_url, link["href"]) if link else base_url

                country_el = item.find(attrs={"class": re.compile(r"country", re.I)})
                country = country_el.get_text(strip=True) if country_el else ""

                outcome_el = item.find(attrs={"class": re.compile(r"outcome|result|status", re.I)})
                outcome = outcome_el.get_text(strip=True) if outcome_el else ""

                if not manufacturer:
                    continue

                text = (
                    f"WHO WHOPIR. Manufacturer: {manufacturer}. "
                    f"Country: {country}. Date: {inspection_date}. Outcome: {outcome}."
                )
                records.append({
                    "id": make_id("WHO-WHOPIR", manufacturer, inspection_date),
                    "source_id": "WHO-WHOPIR",
                    "source_agency": "WHO",
                    "source_type": "public_inspection_report",
                    "manufacturer": manufacturer,
                    "country": country,
                    "inspection_date": inspection_date,
                    "outcome": outcome,
                    "text": text,
                    "date": inspection_date,
                    "source_url": item_url,
                })
            except Exception as e:
                log.debug(f"WHOPIR item error: {e}")
                continue

    return records


def scrape_whopirs() -> list[dict]:
    """Scrape all WHO WHOPIR pages with pagination."""
    all_records = []

    for base_url in WHO_WHOPIR_PAGES:
        log.info(f"Trying WHO WHOPIR URL: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            log.info(f"  No response from {base_url}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        records = parse_whopir_page(soup, base_url)

        if records:
            log.info(f"  Page 1: {len(records)} records")
            all_records.extend(records)

            # Paginate
            page = 2
            while True:
                paginated_url = f"{base_url}?page={page}"
                resp2 = get(paginated_url, delay=1.5, timeout=30.0)
                if not resp2:
                    break
                soup2 = BeautifulSoup(resp2.text, "lxml")
                more = parse_whopir_page(soup2, paginated_url)
                if not more:
                    break
                all_records.extend(more)
                log.info(f"  Page {page}: {len(more)} records")
                page += 1

            break  # Found a working URL
        else:
            log.info(f"  No records at {base_url}, trying next…")
            time.sleep(1.5)

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed WHO WHOPIRs into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["manufacturer", "inspection_date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = scrape_whopirs()
    log.info(f"Total WHOPIR records fetched: {len(all_records)}")

    new_records = []
    for r in all_records:
        key = (r.get("manufacturer", ""), r.get("inspection_date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
