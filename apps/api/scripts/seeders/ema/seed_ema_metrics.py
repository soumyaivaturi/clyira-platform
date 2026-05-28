"""
D2: EMA Annual GMP/GCP Inspection Metrics Seeder
==================================================
Downloads EMA annual inspection metrics PDFs and extracts text about
deficiency categories, percentages, and inspection statistics.
Output: rag_index/ema_inspection_metrics.jsonl

Usage:
    python seed_ema_metrics.py
    python seed_ema_metrics.py --dry-run
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

OUTPUT_FILE = "ema_inspection_metrics.jsonl"

EMA_INSPECTION_PAGES = [
    "https://www.ema.europa.eu/en/about-us/how-we-work/governance-documents/policies-procedures/inspection-activities",
    "https://www.ema.europa.eu/en/human-regulatory-overview/compliance-and-monitoring/good-manufacturing-practice-gmp-compliance/gmp-inspections",
    "https://www.ema.europa.eu/en/about-us/how-we-work/compliance-monitoring/inspection-programme-annual-reports",
    "https://www.ema.europa.eu/en/documents/report",
    "https://www.ema.europa.eu/en/human-regulatory-overview/compliance-and-monitoring/good-clinical-practice-gcp-compliance/gcp-inspections",
]

# Known/likely annual report PDF URL patterns
EMA_ANNUAL_REPORT_PATTERNS = [
    "https://www.ema.europa.eu/documents/report/overview-comments-gmp-inspection-activities-{year}-annual-report_en.pdf",
    "https://www.ema.europa.eu/documents/report/annual-report-gmp-inspections-{year}_en.pdf",
    "https://www.ema.europa.eu/documents/report/european-medicines-agencys-annual-report-{year}_en.pdf",
]

# GCP inspection report patterns
EMA_GCP_PATTERNS = [
    "https://www.ema.europa.eu/documents/report/overview-comments-gcp-inspection-activities-{year}-annual-report_en.pdf",
    "https://www.ema.europa.eu/documents/report/annual-report-gcp-inspections-{year}_en.pdf",
]


def find_pdf_links_on_page(html: str, base_url: str) -> list[tuple[str, str]]:
    """Extract PDF links from an EMA page, with descriptions."""
    soup = BeautifulSoup(html, "lxml")
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        if href.endswith(".pdf"):
            full_url = urljoin(base_url, href)
            # Filter for inspection/metrics/annual report PDFs
            text_combined = (href + " " + link_text).lower()
            if any(kw in text_combined for kw in [
                "annual", "inspection", "report", "metric", "overview", "gmp", "gcp",
                "deficien", "statistic", "activit"
            ]):
                found.append((full_url, link_text))
    return found


def infer_inspection_type(url: str, text: str) -> str:
    combined = (url + " " + text).lower()
    if "gcp" in combined:
        return "GCP"
    if "gdp" in combined:
        return "GDP"
    if "gvp" in combined:
        return "GVP"
    if "gmp" in combined:
        return "GMP"
    if "inspection" in combined:
        return "GMP"
    return "General"


def extract_year_from_url_or_text(url: str, text: str) -> str:
    combined = url + " " + text
    m = re.search(r"\b(20\d{2}|19\d{2})\b", combined)
    return m.group(1) if m else ""


def scrape_ema_inspection_pages() -> list[tuple[str, str]]:
    """Scrape all EMA inspection pages to find PDF links."""
    all_pdfs = []
    seen_urls = set()

    for page_url in EMA_INSPECTION_PAGES:
        log.info(f"Checking EMA page: {page_url}")
        resp = get(page_url, delay=1.5, timeout=30.0)
        if not resp:
            log.info(f"  No response from {page_url}")
            continue

        pdfs = find_pdf_links_on_page(resp.text, page_url)
        for pdf_url, pdf_text in pdfs:
            if pdf_url not in seen_urls:
                seen_urls.add(pdf_url)
                all_pdfs.append((pdf_url, pdf_text))
                log.debug(f"  Found PDF: {pdf_url}")

        # Also follow "annual report" section links
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"]
            if any(kw in text for kw in ["annual report", "inspection report", "overview activities"]):
                full_url = urljoin(page_url, href)
                if full_url not in seen_urls and not full_url.endswith(".pdf"):
                    time.sleep(1.5)
                    sub_resp = get(full_url, delay=1.5, timeout=30.0)
                    if sub_resp:
                        sub_pdfs = find_pdf_links_on_page(sub_resp.text, full_url)
                        for pdf_url, pdf_text in sub_pdfs:
                            if pdf_url not in seen_urls:
                                seen_urls.add(pdf_url)
                                all_pdfs.append((pdf_url, pdf_text))

    log.info(f"Total inspection PDFs found: {len(all_pdfs)}")
    return all_pdfs


def try_known_pdf_patterns() -> list[tuple[str, str]]:
    """Try known/guessed URL patterns for annual reports."""
    found = []
    current_year = 2025  # One year back from today (2026-05)
    for year in range(2010, current_year + 1):
        for pattern in EMA_ANNUAL_REPORT_PATTERNS + EMA_GCP_PATTERNS:
            url = pattern.format(year=year)
            # Don't actually fetch here — just add as candidates
            found.append((url, f"EMA Annual Inspection Report {year}"))
    return found


def process_pdf(pdf_url: str, pdf_text_hint: str) -> dict | None:
    """Download and extract text from an EMA inspection metrics PDF."""
    log.info(f"  Downloading PDF: {pdf_url}")
    resp = get(pdf_url, delay=1.5, timeout=60.0)
    if not resp or len(resp.content) < 1000:
        log.debug(f"  No content from {pdf_url}")
        return None

    text = pdf_to_text(resp.content, max_pages=50)
    if not text or len(text) < 200:
        log.debug(f"  No extractable text from {pdf_url}")
        return None

    year = extract_year_from_url_or_text(pdf_url, pdf_text_hint)
    inspection_type = infer_inspection_type(pdf_url, pdf_text_hint)

    # Try to extract summary metrics section
    summary_text = text[:6000]

    return {
        "id": make_id("EMA-METRICS", year, inspection_type),
        "source_id": "EMA-METRICS",
        "source_agency": "EMA",
        "source_type": "annual_inspection_metrics",
        "year": year,
        "inspection_type": inspection_type,
        "text": summary_text,
        "date": f"{year}-01-01" if year else "",
        "source_url": pdf_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed EMA inspection metrics into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["year", "inspection_type"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    # Collect PDF URLs from EMA pages
    log.info("Scraping EMA inspection pages for annual report PDFs…")
    page_pdfs = scrape_ema_inspection_pages()

    # Also try known URL patterns
    log.info("Trying known annual report URL patterns…")
    pattern_pdfs = try_known_pdf_patterns()

    # Combine, deduplicate
    all_pdf_candidates = []
    seen_urls = set()
    for url, hint in page_pdfs + pattern_pdfs:
        if url not in seen_urls:
            seen_urls.add(url)
            all_pdf_candidates.append((url, hint))

    log.info(f"Total PDF candidates to check: {len(all_pdf_candidates)}")

    new_records = []
    for pdf_url, pdf_hint in all_pdf_candidates:
        try:
            year = extract_year_from_url_or_text(pdf_url, pdf_hint)
            insp_type = infer_inspection_type(pdf_url, pdf_hint)
            key = (year, insp_type)

            if key in existing:
                log.debug(f"  Skipping existing: {year} {insp_type}")
                continue

            record = process_pdf(pdf_url, pdf_hint)
            if record:
                new_records.append(record)
                existing.add(key)
                log.info(f"  Extracted: {year} {insp_type} ({len(record['text'])} chars)")

        except Exception as e:
            log.warning(f"  Error with {pdf_url}: {e}")
            continue

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
