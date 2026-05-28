"""
C2: Health Canada GMP Inspection Summary Reports Seeder
=========================================================
Scrapes GMP Inspection Summary Reports from Health Canada.
Follows links to individual report pages and extracts findings.
Output: rag_index/health_canada_inspection_reports.jsonl

Usage:
    python seed_hc_inspection_reports.py
    python seed_hc_inspection_reports.py --dry-run
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

OUTPUT_FILE = "health_canada_inspection_reports.jsonl"

INDEX_URL = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
    "compliance-enforcement/good-manufacturing-practices/inspection-summary-reports.html"
)
ALTERNATE_URLS = [
    (
        "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
        "compliance-enforcement/good-manufacturing-practices.html"
    ),
    (
        "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
        "compliance-enforcement/establishment-licences/drug-establishment-licence-activities/"
        "inspection-summary-reports.html"
    ),
]


def find_report_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Extract links to individual inspection summary reports."""
    soup = BeautifulSoup(html, "lxml")
    links = []

    # GOV.CA document lists
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # Filter for report-looking links
        if any(kw in href.lower() or kw in text.lower()
               for kw in ["inspection", "summary", "report", "gmp", "isr"]):
            if href.endswith(".html") or href.endswith(".htm") or "/inspection" in href:
                full_url = urljoin(base_url, href)
                if full_url not in [l[0] for l in links]:
                    links.append((full_url, text))

    return links


def extract_report_data(html: str, url: str) -> dict | None:
    """Parse an individual inspection summary report page."""
    soup = BeautifulSoup(html, "lxml")

    # Try to find the main content
    content = soup.find("main") or soup.find("div", id="wb-cont") or soup.find("article") or soup

    full_text = content.get_text(separator=" ", strip=True)

    # Extract company/site name
    company_name = ""
    h1 = soup.find("h1")
    if h1:
        company_name = h1.get_text(strip=True)

    # Extract date
    report_date = ""
    date_patterns = [
        r"\b(\w+ \d{1,2},\s*\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, full_text)
        if m:
            report_date = m.group(1)
            break

    # Extract overall rating
    overall_rating = ""
    rating_patterns = [
        r"overall\s+rating[:\s]+(\w[\w\s-]*?)(?:\.|,|\n|$)",
        r"compliance\s+rating[:\s]+(\w[\w\s-]*?)(?:\.|,|\n|$)",
        r"inspection\s+rating[:\s]+(\w[\w\s-]*?)(?:\.|,|\n|$)",
    ]
    for pattern in rating_patterns:
        m = re.search(pattern, full_text, re.IGNORECASE)
        if m:
            overall_rating = m.group(1).strip()
            break

    # Extract findings
    findings_text = ""
    findings_section = None
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(strip=True).lower()
        if any(kw in heading_text for kw in ["finding", "observation", "deficien", "non-compliance"]):
            findings_section = heading
            break

    if findings_section:
        sibling_text = []
        for sib in findings_section.find_next_siblings():
            if sib.name in ("h2", "h3", "h4"):
                break
            sibling_text.append(sib.get_text(strip=True))
        findings_text = " ".join(sibling_text)[:3000]

    if not findings_text:
        findings_text = full_text[:3000]

    if not company_name and not report_date:
        return None

    text = (
        f"Health Canada GMP Inspection Summary Report. "
        f"Company: {company_name}. Date: {report_date}. "
        f"Rating: {overall_rating}. Findings: {findings_text}"
    )

    return {
        "id": make_id("HC-ISR", company_name, report_date),
        "source_id": "HC-ISR",
        "source_agency": "Health Canada",
        "source_type": "inspection_summary_report",
        "company_name": company_name,
        "report_date": report_date,
        "overall_rating": overall_rating,
        "findings_text": findings_text,
        "text": text,
        "date": report_date,
        "source_url": url,
    }


def scrape_index_page(url: str) -> list[dict]:
    """Scrape the index page and follow links to individual reports."""
    records = []

    resp = get(url, delay=0.5, timeout=30.0)
    if not resp:
        return []

    report_links = find_report_links(resp.text, url)
    log.info(f"  Found {len(report_links)} report links on {url}")

    for report_url, link_text in report_links:
        try:
            time.sleep(0.5)
            report_resp = get(report_url, delay=0.5, timeout=30.0)
            if not report_resp:
                continue

            record = extract_report_data(report_resp.text, report_url)
            if record:
                records.append(record)
                log.debug(f"    Extracted: {record['company_name']} ({record['report_date']})")

        except Exception as e:
            log.debug(f"  Skipping report {report_url}: {e}")
            continue

    # Check for pagination on the index page
    soup = BeautifulSoup(resp.text, "lxml")
    page_num = 2
    while True:
        next_link = soup.find("a", attrs={"rel": "next"}) or soup.find("a", string=re.compile(r"next|>", re.I))
        if not next_link:
            break

        next_href = next_link.get("href", "")
        paginated_url = urljoin(url, next_href) if next_href else f"{url}?page={page_num}"

        resp2 = get(paginated_url, delay=0.5, timeout=30.0)
        if not resp2:
            break

        more_links = find_report_links(resp2.text, paginated_url)
        log.info(f"  Page {page_num}: {len(more_links)} more report links")

        for report_url, _ in more_links:
            try:
                time.sleep(0.5)
                report_resp = get(report_url, delay=0.5, timeout=30.0)
                if not report_resp:
                    continue
                record = extract_report_data(report_resp.text, report_url)
                if record:
                    records.append(record)
            except Exception as e:
                log.debug(f"  Skipping report: {e}")
                continue

        soup = BeautifulSoup(resp2.text, "lxml")
        page_num += 1

        if not more_links:
            break

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed Health Canada inspection summary reports into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["company_name", "report_date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    urls_to_try = [INDEX_URL] + ALTERNATE_URLS
    for url in urls_to_try:
        log.info(f"Scraping inspection reports from: {url}")
        records = scrape_index_page(url)
        log.info(f"  Got {len(records)} records from {url}")
        all_records.extend(records)
        if records:
            break  # If primary URL worked, don't need alternates
        time.sleep(0.5)

    new_records = []
    for r in all_records:
        key = (r.get("company_name", ""), r.get("report_date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
