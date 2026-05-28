"""
G1: CDSCO Not-of-Standard-Quality (NSQ) Drug Alerts Seeder
=============================================================
Scrapes CDSCO not-of-standard-quality drug alerts from the CDSCO website.
Downloads monthly PDF lists, parses, extracts drug name, manufacturer, batch, failure reason.
Output: rag_index/cdsco_nsq.jsonl

Usage:
    python seed_cdsco.py
    python seed_cdsco.py --dry-run
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

OUTPUT_FILE = "cdsco_nsq.jsonl"

CDSCO_BASE = "https://cdsco.gov.in"
CDSCO_NSQ_PAGE = "https://cdsco.gov.in/opencms/opencms/en/Notifications/Alerts/"
CDSCO_ALERTS_ALT = "https://cdsco.gov.in/opencms/opencms/en/Consumer/Alerts/"
CDSCO_NSQ_ALT2 = "https://cdsco.gov.in/opencms/opencms/en/Notifications/"
CDSCO_SPURT_SHEET_URL = "https://cdsco.gov.in/opencms/opencms/en/Notifications/Alerts/"

# CDSCO publishes NSQ alerts as a downloadable xlsx too
CDSCO_NSQ_LIST_URLS = [
    "https://cdsco.gov.in/opencms/opencms/en/Notifications/Alerts/",
    "https://cdsco.gov.in/opencms/opencms/en/Consumer/Alerts/",
    "https://cdsco.gov.in/opencms/opencms/en/Notifications/NSQ-Drugs-List/",
]


def extract_date_from_text(text: str) -> str:
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\w+\s+\d{4})\b",
        r"\b(\d{1,2}\s+\w+\s+\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def parse_nsq_from_pdf_text(text: str, source_url: str) -> list[dict]:
    """Parse NSQ records from extracted PDF text."""
    records = []
    lines = text.split("\n")

    # Try to detect table rows in PDF
    # Common CDSCO NSQ format: Drug Name | Manufacturer | Batch | Failure reason | Date
    current_record = {}

    # Pattern-based extraction from PDF text
    # CDSCO NSQ typically lists: S.No., Name of Drug, Name of Manufacturer, Batch No., Failure Parameter
    drug_line_pattern = re.compile(
        r"(?:^|\n)\s*\d+[\.\)]\s+"
        r"([A-Za-z][A-Za-z0-9\s\(\)\-\+\.]+?)\s+"
        r"(?:M/s\.?\s+|Shri\s+|M/S\.?\s+)?([A-Za-z][A-Za-z0-9\s\&\.\,\-]+?)\s+"
        r"(?:Batch\s+(?:No\.?\s+)?|B\.No\.?\s*)([A-Z0-9\-\/]+)\s+"
        r"(.{10,200}?)(?:\n|$)",
        re.IGNORECASE | re.MULTILINE
    )

    for m in drug_line_pattern.finditer(text):
        try:
            drug_name = m.group(1).strip()
            manufacturer = m.group(2).strip()
            batch_number = m.group(3).strip()
            failure_reason = m.group(4).strip()

            date = extract_date_from_text(source_url + " " + text[:500])

            if len(drug_name) < 3 or len(drug_name) > 200:
                continue

            record_text = (
                f"CDSCO Not of Standard Quality. Drug: {drug_name}. "
                f"Manufacturer: {manufacturer}. Batch: {batch_number}. "
                f"Failure reason: {failure_reason}. Date: {date}."
            )

            records.append({
                "id": make_id("CDSCO-NSQ", drug_name, batch_number),
                "source_id": "CDSCO-NSQ",
                "source_agency": "CDSCO",
                "source_type": "not_of_standard_quality",
                "drug_name": drug_name,
                "manufacturer": manufacturer,
                "batch_number": batch_number,
                "failure_reason": failure_reason,
                "date": date,
                "text": record_text,
                "source_url": source_url,
            })
        except Exception as e:
            log.debug(f"PDF line parse error: {e}")
            continue

    if not records:
        # Fallback: line-by-line extraction
        batch_pattern = re.compile(r"[A-Z]{1,4}[/-]?\d{3,8}[A-Z]?", re.IGNORECASE)
        fail_keywords = ["not conform", "fail", "dissolution", "assay", "identification", "sterility", "purity", "content"]

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or len(line) < 5:
                i += 1
                continue

            batch_match = batch_pattern.search(line)
            if batch_match:
                batch_num = batch_match.group(0)
                # Look for failure reason nearby
                context = " ".join(lines[max(0, i-2):i+3])
                failure_reason = ""
                for kw in fail_keywords:
                    if kw in context.lower():
                        # Extract the sentence containing the keyword
                        sentences = re.split(r"[.;]", context)
                        for s in sentences:
                            if kw in s.lower():
                                failure_reason = s.strip()
                                break
                        break

                if failure_reason:
                    drug_name = line.split(batch_num)[0].strip()[:100]
                    date = extract_date_from_text(source_url + " " + text[:500])
                    record_text = f"CDSCO NSQ. Drug: {drug_name}. Batch: {batch_num}. {failure_reason}."
                    records.append({
                        "id": make_id("CDSCO-NSQ", drug_name, batch_num),
                        "source_id": "CDSCO-NSQ",
                        "source_agency": "CDSCO",
                        "source_type": "not_of_standard_quality",
                        "drug_name": drug_name,
                        "manufacturer": "",
                        "batch_number": batch_num,
                        "failure_reason": failure_reason[:500],
                        "date": date,
                        "text": record_text,
                        "source_url": source_url,
                    })
            i += 1

    return records


def parse_nsq_html_table(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse NSQ records from HTML tables on CDSCO pages."""
    records = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        col = {}
        for i, h in enumerate(headers):
            if "drug" in h or "name" in h or "medicine" in h:
                col.setdefault("drug_name", i)
            elif "manufacturer" in h or "firm" in h or "company" in h:
                col.setdefault("manufacturer", i)
            elif "batch" in h or "lot" in h or "b.no" in h:
                col.setdefault("batch_number", i)
            elif "fail" in h or "reason" in h or "param" in h or "remark" in h:
                col.setdefault("failure_reason", i)
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

                drug_name = cell("drug_name", 1)  # Often col 0 is S.No
                manufacturer = cell("manufacturer", 2)
                batch_number = cell("batch_number", 3)
                failure_reason = cell("failure_reason", 4)
                date = cell("date", 5)

                if not drug_name:
                    drug_name = cell("drug_name", 0)

                if not drug_name or len(drug_name) < 2:
                    continue

                link = row.find("a", href=True)
                row_url = urljoin(base_url, link["href"]) if link else base_url

                text = (
                    f"CDSCO NSQ Drug Alert. Drug: {drug_name}. "
                    f"Manufacturer: {manufacturer}. Batch: {batch_number}. "
                    f"Failure: {failure_reason}. Date: {date}."
                )

                records.append({
                    "id": make_id("CDSCO-NSQ", drug_name, batch_number),
                    "source_id": "CDSCO-NSQ",
                    "source_agency": "CDSCO",
                    "source_type": "not_of_standard_quality",
                    "drug_name": drug_name,
                    "manufacturer": manufacturer,
                    "batch_number": batch_number,
                    "failure_reason": failure_reason,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"CDSCO table row error: {e}")
                continue

    return records


def find_pdf_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    """Find PDF links on CDSCO page."""
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if href.endswith(".pdf"):
            full_url = urljoin(base_url, href)
            if any(kw in (href + text).lower() for kw in
                   ["nsq", "not of standard", "alert", "notification", "drug"]):
                pdfs.append((full_url, text))
    return pdfs


def scrape_cdsco() -> list[dict]:
    """Main CDSCO scraper — tries HTML tables then PDFs."""
    all_records = []

    for base_url in CDSCO_NSQ_LIST_URLS:
        log.info(f"Trying CDSCO URL: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            log.info(f"  No response from {base_url}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # Try HTML table first
        table_records = parse_nsq_html_table(soup, base_url)
        if table_records:
            log.info(f"  HTML table: {len(table_records)} records")
            all_records.extend(table_records)

        # Find and process PDFs
        pdf_links = find_pdf_links(soup, base_url)
        log.info(f"  Found {len(pdf_links)} PDF links")

        for pdf_url, hint in pdf_links:
            try:
                time.sleep(1.5)
                resp_pdf = get(pdf_url, delay=1.5, timeout=60.0)
                if not resp_pdf or len(resp_pdf.content) < 500:
                    continue

                text = pdf_to_text(resp_pdf.content, max_pages=100)
                if not text:
                    continue

                pdf_records = parse_nsq_from_pdf_text(text, pdf_url)
                if pdf_records:
                    log.info(f"  PDF {hint}: {len(pdf_records)} records")
                    all_records.extend(pdf_records)
            except Exception as e:
                log.warning(f"  Error processing PDF {pdf_url}: {e}")
                continue

        # Paginate
        page = 2
        while True:
            paginated = f"{base_url}?page={page}"
            resp2 = get(paginated, delay=1.5, timeout=30.0)
            if not resp2:
                break
            soup2 = BeautifulSoup(resp2.text, "lxml")
            more = parse_nsq_html_table(soup2, paginated)
            if not more:
                break
            all_records.extend(more)
            log.info(f"  Page {page}: {len(more)} records")
            page += 1

        if all_records:
            break  # Found working URL
        time.sleep(1.5)

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed CDSCO NSQ drug alerts into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["drug_name", "batch_number"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = scrape_cdsco()
    log.info(f"Total CDSCO NSQ records: {len(all_records)}")

    new_records = []
    for r in all_records:
        key = (r.get("drug_name", ""), r.get("batch_number", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
