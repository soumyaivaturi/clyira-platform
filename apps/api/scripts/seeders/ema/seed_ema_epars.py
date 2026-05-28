"""
D1: EMA EPAR Quality Assessment Seeder
========================================
Downloads EMA European Public Assessment Report (EPAR) quality assessment sections.
Uses the EMA medicines data download CSV to find products, then fetches PDFs.
Output: rag_index/ema_epars_quality.jsonl

Usage:
    python seed_ema_epars.py
    python seed_ema_epars.py --dry-run
"""
import argparse
import csv
import io
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

OUTPUT_FILE = "ema_epars_quality.jsonl"

EMA_DOWNLOAD_PAGE = "https://www.ema.europa.eu/en/medicines/download-medicine-data"
EMA_EPAR_CSV_URL = (
    "https://www.ema.europa.eu/sites/default/files/Medicines_output_european_public_assessment_reports.xlsx"
)
EMA_EPAR_CSV_FALLBACK = (
    "https://www.ema.europa.eu/en/documents/other/"
    "european-public-assessment-reports-epar-dataset_en.xlsx"
)
EMA_PRODUCT_BASE = "https://www.ema.europa.eu/en/medicines/human"
EMA_EPAR_BASE = "https://www.ema.europa.eu"

# Quality assessment PDF URL pattern
EPAR_PDF_PATTERN = (
    "https://www.ema.europa.eu/documents/assessment-report/"
    "{slug}-epar-public-assessment-report_en.pdf"
)


def find_epar_data_url(html: str) -> str | None:
    """Find the EPAR data download URL from the EMA download page."""
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ("epar" in href.lower() or "assessment" in href.lower() or "medicines_output" in href.lower()):
            if href.endswith((".xlsx", ".xls", ".csv")):
                return urljoin(EMA_DOWNLOAD_PAGE, href)
    return None


def load_epar_catalog_xlsx(content: bytes) -> list[dict]:
    """Parse the EMA EPAR catalog Excel file."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(c).strip().lower() if c else "" for c in rows[0]]

        col = {}
        for i, h in enumerate(headers):
            if "medicine" in h and "name" in h:
                col.setdefault("product_name", i)
            elif "product" in h and "name" in h:
                col.setdefault("product_name", i)
            elif "procedure" in h and ("number" in h or "num" in h):
                col.setdefault("procedure_number", i)
            elif "therapeutic" in h or "therapy" in h:
                col.setdefault("therapeutic_area", i)
            elif "date" in h and "opinion" in h:
                col.setdefault("opinion_date", i)
            elif "date" in h and ("authoris" in h or "approv" in h):
                col.setdefault("date", i)
            elif "url" in h or "link" in h:
                col.setdefault("url", i)
            elif "epar" in h and "url" in h:
                col["url"] = i

        def cell(row, key):
            idx = col.get(key)
            return str(row[idx]).strip() if idx is not None and idx < len(row) and row[idx] is not None else ""

        records = []
        for row in rows[1:]:
            product_name = cell(row, "product_name")
            procedure_number = cell(row, "procedure_number")
            therapeutic_area = cell(row, "therapeutic_area")
            date = cell(row, "date") or cell(row, "opinion_date")
            url = cell(row, "url")

            if not product_name and not procedure_number:
                continue

            records.append({
                "product_name": product_name,
                "procedure_number": procedure_number,
                "therapeutic_area": therapeutic_area,
                "date": date,
                "catalog_url": url,
            })

        wb.close()
        log.info(f"Loaded {len(records)} products from EPAR catalog")
        return records
    except ImportError:
        log.error("openpyxl not installed; run: pip install openpyxl")
        return []
    except Exception as e:
        log.error(f"Failed to parse EPAR catalog: {e}")
        return []


def load_epar_catalog_csv(content: bytes) -> list[dict]:
    """Fallback: parse CSV format."""
    try:
        decoded = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(decoded))
        records = []
        for row in reader:
            product_name = ""
            for k in row:
                if "medicine" in k.lower() or "product" in k.lower():
                    product_name = row[k]
                    break
            procedure_number = row.get("Procedure Number", row.get("procedure_number", ""))
            therapeutic_area = row.get("Therapeutic Area", row.get("therapeutic_area", ""))
            date = row.get("Date", row.get("date", ""))
            if product_name or procedure_number:
                records.append({
                    "product_name": product_name,
                    "procedure_number": procedure_number,
                    "therapeutic_area": therapeutic_area,
                    "date": date,
                    "catalog_url": "",
                })
        return records
    except Exception as e:
        log.error(f"CSV parse error: {e}")
        return []


def slug_from_name(name: str) -> str:
    """Convert product name to URL slug."""
    slug = re.sub(r"[^a-z0-9\s-]", "", name.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:60]


def find_quality_pdf_url(product_name: str, procedure_number: str, catalog_url: str) -> str | None:
    """Find the quality assessment PDF URL for a product."""
    # Try catalog URL first
    if catalog_url and catalog_url.startswith("http"):
        resp = get(catalog_url, delay=1.5, timeout=30.0)
        if resp:
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True).lower()
                if "public-assessment" in href.lower() and href.endswith(".pdf"):
                    return urljoin(EMA_EPAR_BASE, href)
                if "quality" in link_text and href.endswith(".pdf"):
                    return urljoin(EMA_EPAR_BASE, href)
                if "epar" in href.lower() and "assessment" in href.lower() and href.endswith(".pdf"):
                    return urljoin(EMA_EPAR_BASE, href)

    # Try slug-based URL pattern
    slug = slug_from_name(product_name)
    if slug:
        candidate_url = f"{EMA_EPAR_BASE}/documents/assessment-report/{slug}-epar-public-assessment-report_en.pdf"
        return candidate_url

    return None


def fetch_and_extract_quality_pdf(pdf_url: str) -> str:
    """Download a PDF and extract quality-relevant text."""
    resp = get(pdf_url, delay=1.5, timeout=60.0)
    if not resp or len(resp.content) < 1000:
        return ""

    text = pdf_to_text(resp.content, max_pages=50)
    if not text:
        return ""

    # Extract quality-relevant sections
    quality_sections = []
    lines = text.split("\n")
    in_quality = False
    quality_keywords = ["quality", "pharmaceutical", "manufacturing", "gmp", "specifications", "analytical"]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["2. quality", "quality aspects", "2.1 introduction", "pharmaceutical development"]):
            in_quality = True
        if in_quality:
            quality_sections.append(line)
            if len(quality_sections) > 300:  # Limit to ~300 lines of quality section
                break

    if quality_sections:
        return "\n".join(quality_sections)[:8000]

    # Fallback: return first 4000 chars
    return text[:4000]


def main():
    parser = argparse.ArgumentParser(description="Seed EMA EPAR quality assessments into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    parser.add_argument("--max-products", type=int, default=0, help="Max products to process (0 = all)")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["procedure_number", "source_type"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    # Step 1: Get the EPAR catalog
    catalog_content = None
    catalog_source = ""

    log.info("Fetching EMA EPAR catalog from download page…")
    page_resp = get(EMA_DOWNLOAD_PAGE, delay=1.5, timeout=30.0)
    if page_resp:
        catalog_url = find_epar_data_url(page_resp.text)
        if catalog_url:
            log.info(f"  Found catalog URL: {catalog_url}")
            time.sleep(1.5)
            cat_resp = get(catalog_url, delay=1.5, timeout=120.0)
            if cat_resp and len(cat_resp.content) > 1000:
                catalog_content = cat_resp.content
                catalog_source = catalog_url

    if not catalog_content:
        for fallback_url in [EMA_EPAR_CSV_URL, EMA_EPAR_CSV_FALLBACK]:
            log.info(f"  Trying catalog fallback: {fallback_url}")
            cat_resp = get(fallback_url, delay=1.5, timeout=120.0)
            if cat_resp and len(cat_resp.content) > 1000:
                catalog_content = cat_resp.content
                catalog_source = fallback_url
                break

    if not catalog_content:
        log.warning("Could not download EMA EPAR catalog — exiting")
        return

    # Parse catalog
    if catalog_source.endswith((".xlsx", ".xls")):
        products = load_epar_catalog_xlsx(catalog_content)
    else:
        products = load_epar_catalog_csv(catalog_content)

    if not products:
        log.warning("No products found in EPAR catalog")
        return

    log.info(f"Total products in catalog: {len(products)}")

    if args.max_products > 0:
        products = products[:args.max_products]
        log.info(f"Limited to {len(products)} products")

    new_records = []
    for i, product in enumerate(products):
        product_name = product["product_name"]
        procedure_number = product["procedure_number"]

        # Dedup check
        key = (procedure_number, "epar_quality_assessment")
        if key in existing:
            continue

        log.info(f"  [{i+1}/{len(products)}] {product_name} ({procedure_number})")

        try:
            pdf_url = find_quality_pdf_url(product_name, procedure_number, product.get("catalog_url", ""))
            if not pdf_url:
                log.debug(f"    No PDF URL found for {product_name}")
                continue

            log.debug(f"    Fetching PDF: {pdf_url}")
            time.sleep(1.5)
            quality_text = fetch_and_extract_quality_pdf(pdf_url)

            if not quality_text or len(quality_text) < 200:
                log.debug(f"    No quality text extracted for {product_name}")
                continue

            date = product.get("date", "")
            if date and len(str(date)) > 10:
                date = str(date)[:10]

            record = {
                "id": make_id("EMA-EPAR", procedure_number, "quality"),
                "source_id": "EMA-EPAR",
                "source_agency": "EMA",
                "source_type": "epar_quality_assessment",
                "product_name": product_name,
                "procedure_number": procedure_number,
                "therapeutic_area": product.get("therapeutic_area", ""),
                "date": str(date),
                "text": quality_text,
                "source_url": pdf_url,
            }

            new_records.append(record)
            existing.add(key)

            # Write in batches
            if len(new_records) % 20 == 0 and not args.dry_run:
                append_records(out_path, new_records[-20:], False, log)
                log.info(f"  Intermediate write: {len(new_records)} total new records")

        except Exception as e:
            log.warning(f"  Error processing {product_name}: {e}")
            continue

    # Write remaining
    if args.dry_run:
        written = append_records(out_path, new_records[:5], args.dry_run, log)
        log.info(f"DRY RUN — would write {len(new_records)} records")
    else:
        remainder = new_records[-(len(new_records) % 20 or 20):]
        if remainder:
            append_records(out_path, remainder, False, log)
        written = len(new_records)
        log.info(f"Wrote {written} total records to {out_path}")


if __name__ == "__main__":
    main()
