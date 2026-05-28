"""
C1: Health Canada DHPID (Drug and Health Product Inspections Database) Seeder
==============================================================================
Fetches GMP inspection records from Health Canada's inspection database.
Tries JSON API first, falls back to HTML scraping.
Output: rag_index/health_canada_inspections.jsonl

Usage:
    python seed_hc_dhpid.py
    python seed_hc_dhpid.py --dry-run
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

OUTPUT_FILE = "health_canada_inspections.jsonl"

# Health Canada DHPID endpoints
HC_API_BASE = "https://health-products.canada.ca/api/consultation"
HC_DHPID_SEARCH = "https://health-products.canada.ca/api/dhpid/inspection"
HC_SITE_PROFILES = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
    "compliance-enforcement/good-manufacturing-practices/site-profiles.html"
)
HC_INSPECTION_LIST = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
    "compliance-enforcement/good-manufacturing-practices/inspections.html"
)
HC_COMPLIANCE_BASE = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/"
    "compliance-enforcement/good-manufacturing-practices"
)


def fetch_via_api(page: int = 0, per_page: int = 100) -> list[dict]:
    """Try Health Canada JSON API endpoints."""
    api_urls = [
        f"{HC_API_BASE}/?lang=en&type=gmpInspection&page={page}&per_page={per_page}",
        f"{HC_DHPID_SEARCH}?lang=en&page={page}&limit={per_page}",
        f"https://health-products.canada.ca/api/inspection/gmp?lang=en&page={page}&limit={per_page}",
    ]

    for url in api_urls:
        resp = get(url, delay=0.5, timeout=30.0)
        if not resp:
            continue
        try:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data
            if isinstance(data, dict):
                for key in ("results", "data", "inspections", "items", "records"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except Exception:
            continue

    return []


def parse_api_record(raw: dict) -> dict | None:
    """Map a Health Canada API inspection record to our schema."""
    try:
        ref_num = (
            raw.get("referenceNumber") or
            raw.get("reference_number") or
            raw.get("id") or
            raw.get("inspectionId") or
            ""
        )
        company = (
            raw.get("companyName") or
            raw.get("company_name") or
            raw.get("siteName") or
            raw.get("site_name") or
            ""
        )
        country = raw.get("country", raw.get("countryCode", ""))
        insp_date = (
            raw.get("inspectionDate") or
            raw.get("inspection_date") or
            raw.get("date") or
            ""
        )
        rating = (
            raw.get("rating") or
            raw.get("overallRating") or
            raw.get("complianceRating") or
            ""
        )
        product_type = (
            raw.get("productType") or
            raw.get("product_type") or
            raw.get("licenceType") or
            ""
        )

        if not ref_num and not company:
            return None

        text = (
            f"Health Canada GMP Inspection. Company: {company}. "
            f"Country: {country}. Date: {insp_date}. "
            f"Rating: {rating}. Product type: {product_type}. "
            f"Reference: {ref_num}."
        )

        return {
            "id": make_id("HC-DHPID", ref_num or company, insp_date),
            "source_id": "HC-DHPID",
            "source_agency": "Health Canada",
            "source_type": "gmp_inspection",
            "reference_number": str(ref_num),
            "company_name": company,
            "country": country,
            "inspection_date": str(insp_date)[:10],
            "rating": rating,
            "product_type": product_type,
            "text": text,
            "date": str(insp_date)[:10],
            "source_url": HC_API_BASE,
        }
    except Exception as e:
        log.debug(f"parse_api_record error: {e}")
        return None


def scrape_inspection_html_page(url: str) -> list[dict]:
    """Scrape inspection records from an HTML page."""
    records = []
    resp = get(url, delay=0.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # Try tables first
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        # Map header positions
        col = {}
        for i, h in enumerate(headers):
            if any(k in h for k in ["company", "establishment", "site", "firm"]):
                col.setdefault("company", i)
            elif any(k in h for k in ["reference", "number", "id"]):
                col.setdefault("reference", i)
            elif any(k in h for k in ["country"]):
                col.setdefault("country", i)
            elif any(k in h for k in ["date", "inspection date"]):
                col.setdefault("date", i)
            elif any(k in h for k in ["rating", "result", "outcome", "compliance"]):
                col.setdefault("rating", i)
            elif any(k in h for k in ["product", "type", "licence"]):
                col.setdefault("product_type", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key):
                    idx = col.get(key)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                company = cell("company") or cols[0].get_text(strip=True)
                ref_num = cell("reference")
                country = cell("country")
                date = cell("date")
                rating = cell("rating")
                product_type = cell("product_type")

                if not company:
                    continue

                link = row.find("a", href=True)
                row_url = urljoin(url, link["href"]) if link else url

                text = (
                    f"Health Canada GMP Inspection. Company: {company}. "
                    f"Country: {country}. Date: {date}. Rating: {rating}. "
                    f"Product type: {product_type}."
                )

                records.append({
                    "id": make_id("HC-DHPID", ref_num or company, date),
                    "source_id": "HC-DHPID",
                    "source_agency": "Health Canada",
                    "source_type": "gmp_inspection",
                    "reference_number": ref_num,
                    "company_name": company,
                    "country": country,
                    "inspection_date": date,
                    "rating": rating,
                    "product_type": product_type,
                    "text": text,
                    "date": date,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Skipping row: {e}")
                continue

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed Health Canada DHPID inspection records into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["reference_number"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    # Try API pagination
    log.info("Trying Health Canada JSON API…")
    page = 0
    while True:
        batch = fetch_via_api(page=page, per_page=100)
        if not batch:
            if page == 0:
                log.info("  API returned no results, falling back to HTML scraping")
            break
        log.info(f"  API page {page}: {len(batch)} records")
        for raw in batch:
            parsed = parse_api_record(raw)
            if parsed:
                all_records.append(parsed)
        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.5)

    if not all_records:
        # Fallback to HTML pages
        html_urls = [HC_SITE_PROFILES, HC_INSPECTION_LIST]
        for url in html_urls:
            log.info(f"  Scraping HTML: {url}")
            page_records = scrape_inspection_html_page(url)
            log.info(f"    Got {len(page_records)} records")
            all_records.extend(page_records)

            # Follow pagination on HTML pages
            page_num = 2
            while True:
                paginated_url = f"{url}?page={page_num}"
                resp = get(paginated_url, delay=0.5, timeout=30.0)
                if not resp:
                    break
                soup = BeautifulSoup(resp.text, "lxml")
                next_link = soup.find("a", attrs={"rel": "next"}) or soup.find("a", string=re.compile(r"next|>", re.I))
                more = scrape_inspection_html_page(paginated_url)
                if not more:
                    break
                all_records.extend(more)
                log.info(f"    Page {page_num}: {len(more)} records")
                if not next_link:
                    break
                page_num += 1
                time.sleep(0.5)

    new_records = []
    for r in all_records:
        key = (r.get("reference_number", ""),)
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
