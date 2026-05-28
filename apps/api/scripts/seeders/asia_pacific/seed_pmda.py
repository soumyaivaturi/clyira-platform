"""
F2: PMDA (Pharmaceuticals and Medical Devices Agency) Annual GMP Reports Seeder
================================================================================
Scrapes PMDA English GMP reports and approved drug information.
Downloads English PDF reports, extracts text.
Output: rag_index/pmda_annual_reports.jsonl

Usage:
    python seed_pmda.py
    python seed_pmda.py --dry-run
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

OUTPUT_FILE = "pmda_annual_reports.jsonl"

PMDA_BASE = "https://www.pmda.go.jp"
PMDA_GMP_PAGE = "https://www.pmda.go.jp/english/review-services/gmp-qms-gctp/0003.html"
PMDA_APPROVED_PAGE = "https://www.pmda.go.jp/english/review-services/reviews/approved-information/drugs/0002.html"
PMDA_ENGLISH_TOP = "https://www.pmda.go.jp/english/"

# Additional PMDA pages that might have annual reports
PMDA_ANNUAL_REPORT_PAGES = [
    "https://www.pmda.go.jp/english/about-pmda/annual-report/0001.html",
    "https://www.pmda.go.jp/english/about-pmda/annual-report/",
    "https://www.pmda.go.jp/english/about-pmda/publications/0001.html",
    "https://www.pmda.go.jp/english/review-services/gmp-qms-gctp/",
]


def extract_year_from_url_or_text(url: str, text: str) -> str:
    combined = url + " " + text
    m = re.search(r"\b(20\d{2}|FY\s*20\d{2})\b", combined)
    if m:
        year_str = m.group(1)
        m2 = re.search(r"20\d{2}", year_str)
        return m2.group(0) if m2 else year_str
    return ""


def find_pdf_links(html: str, base_url: str) -> list[tuple[str, str]]:
    """Find English PDF report links on a PMDA page."""
    soup = BeautifulSoup(html, "lxml")
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        if not href.endswith(".pdf"):
            continue

        href_lower = href.lower()
        text_lower = link_text.lower()
        combined = href_lower + " " + text_lower

        if any(kw in combined for kw in [
            "annual", "report", "gmp", "qms", "gctp", "inspection",
            "review", "activity", "outline", "overview"
        ]):
            full_url = urljoin(base_url, href)
            found.append((full_url, link_text))

    return found


def find_english_subpages(html: str, base_url: str) -> list[str]:
    """Find English sub-pages that might have annual report PDFs."""
    soup = BeautifulSoup(html, "lxml")
    subpages = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        href_lower = href.lower()
        if any(kw in text or kw in href_lower for kw in [
            "annual", "report", "gmp", "inspection", "activity", "outline"
        ]):
            if href.endswith((".html", ".htm")) or href.endswith("/"):
                full_url = urljoin(base_url, href)
                if full_url not in subpages and "pmda.go.jp" in full_url:
                    subpages.append(full_url)
    return subpages[:10]  # Limit to 10 subpages


def process_pdf(pdf_url: str, pdf_hint: str) -> dict | None:
    """Download and process a PMDA PDF."""
    log.info(f"  Downloading PMDA PDF: {pdf_url}")
    resp = get(pdf_url, delay=1.5, timeout=60.0)
    if not resp or len(resp.content) < 1000:
        log.debug(f"  No content from {pdf_url}")
        return None

    text = pdf_to_text(resp.content, max_pages=50)
    if not text or len(text) < 200:
        log.debug(f"  No text extracted from {pdf_url}")
        return None

    year = extract_year_from_url_or_text(pdf_url, pdf_hint + " " + text[:200])

    return {
        "id": make_id("PMDA", year or pdf_url),
        "source_id": "PMDA",
        "source_agency": "PMDA",
        "source_type": "annual_gmp_report",
        "year": year,
        "text": text[:6000],
        "date": f"{year}-01-01" if year and year.isdigit() else "",
        "source_url": pdf_url,
    }


def scrape_pmda_pages() -> list[dict]:
    """Scrape PMDA English pages for GMP report PDFs."""
    all_pdfs = []
    seen_urls = set()
    records = []

    pages_to_check = [PMDA_GMP_PAGE, PMDA_ENGLISH_TOP] + PMDA_ANNUAL_REPORT_PAGES

    for page_url in pages_to_check:
        log.info(f"Checking PMDA page: {page_url}")
        resp = get(page_url, delay=1.5, timeout=30.0)
        if not resp:
            log.info(f"  No response from {page_url}")
            continue

        pdfs = find_pdf_links(resp.text, page_url)
        for pdf_url, hint in pdfs:
            if pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                all_pdfs.append((pdf_url, hint))
                log.info(f"  Found PDF: {pdf_url}")

        # Check sub-pages
        subpages = find_english_subpages(resp.text, page_url)
        for sub_url in subpages:
            if sub_url in seen_urls:
                continue
            time.sleep(1.5)
            sub_resp = get(sub_url, delay=1.5, timeout=30.0)
            if not sub_resp:
                continue
            sub_pdfs = find_pdf_links(sub_resp.text, sub_url)
            for pdf_url, hint in sub_pdfs:
                if pdf_url not in seen_urls:
                    seen_urls.add(pdf_url)
                    all_pdfs.append((pdf_url, hint))
                    log.info(f"    Found sub-page PDF: {pdf_url}")

    # Also try PMDA approved drugs page for documents
    log.info(f"Checking PMDA approved drugs page: {PMDA_APPROVED_PAGE}")
    resp = get(PMDA_APPROVED_PAGE, delay=1.5, timeout=30.0)
    if resp:
        pdfs = find_pdf_links(resp.text, PMDA_APPROVED_PAGE)
        for pdf_url, hint in pdfs:
            if pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                all_pdfs.append((pdf_url, hint))

    log.info(f"Total PMDA PDFs to process: {len(all_pdfs)}")

    for pdf_url, hint in all_pdfs:
        try:
            time.sleep(1.5)
            record = process_pdf(pdf_url, hint)
            if record:
                records.append(record)
                log.info(f"  Extracted: year={record['year']}, {len(record['text'])} chars")
        except Exception as e:
            log.warning(f"  Error processing {pdf_url}: {e}")
            continue

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed PMDA annual GMP reports into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["year"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = scrape_pmda_pages()
    log.info(f"Total PMDA records: {len(all_records)}")

    new_records = []
    for r in all_records:
        key = (r.get("year", r.get("source_url", "")),)
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
