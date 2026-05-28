"""
E3: WHO Substandard/Falsified Product Alerts Seeder
=====================================================
Scrapes WHO medical product alerts for substandard and falsified products.
Paginate all alert listings.
Output: rag_index/who_product_alerts.jsonl

Usage:
    python seed_who_alerts.py
    python seed_who_alerts.py --dry-run
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

OUTPUT_FILE = "who_product_alerts.jsonl"

WHO_SF_BASE_URL = (
    "https://www.who.int/teams/health-product-policy-and-standards/standards-and-specifications/"
    "norms-and-standards-for-pharmaceuticals/substandard-and-falsified-medical-products"
)
WHO_ALERTS_LIST_URL = (
    "https://www.who.int/teams/health-product-policy-and-standards/standards-and-specifications/"
    "norms-and-standards-for-pharmaceuticals/substandard-and-falsified-medical-products/"
    "sf-medical-products-alerts"
)
WHO_ANNUAL_REPORT_URL = "https://www.who.int/publications/i/item/WHO-MVP-EMP-SAV-2023-01"
WHO_SF_SEARCH = "https://www.who.int/news?sf_status=true&sf_type=medical_product"
WHO_SF_ALERTS_ALT = "https://www.who.int/news/item"

WHO_BASE = "https://www.who.int"

# WHO Medical Product Alert API if available
WHO_API_ALERTS = "https://www.who.int/api/news/newsitems?sf=true&$top=100&$skip={skip}"


def fetch_api_alerts(skip: int = 0) -> list[dict]:
    """Try WHO JSON API for alerts."""
    url = WHO_API_ALERTS.format(skip=skip)
    resp = get(url, delay=1.5, timeout=30.0)
    if not resp:
        return []
    try:
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("value", "results", "items", "data"):
                if key in data and isinstance(data[key], list):
                    return data[key]
    except Exception:
        pass
    return []


def parse_api_alert(raw: dict) -> dict | None:
    """Parse a WHO API alert record."""
    try:
        title = raw.get("Title") or raw.get("title") or raw.get("name") or ""
        if isinstance(title, dict):
            title = title.get("en", "") or str(title)

        date = (
            raw.get("PublicationDate") or
            raw.get("publication_date") or
            raw.get("date") or
            raw.get("Date") or
            ""
        )
        if isinstance(date, str) and len(date) > 10:
            date = date[:10]

        desc = raw.get("Summary") or raw.get("summary") or raw.get("body") or ""
        if isinstance(desc, dict):
            desc = desc.get("en", "") or str(desc)

        url = raw.get("Url") or raw.get("url") or raw.get("link") or WHO_SF_BASE_URL

        if not title:
            return None

        # Extract product/manufacturer info from text
        product_name = title
        manufacturer = ""
        country = ""

        # Common patterns in SF alerts
        m = re.search(r"(?:manufacturer|produced by|manufactured by)[:\s]+([^.]+)", desc, re.I)
        if m:
            manufacturer = m.group(1).strip()[:200]
        m = re.search(r"(?:country|origin|from)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", desc, re.I)
        if m:
            country = m.group(1).strip()[:100]

        text = f"WHO Substandard/Falsified Alert. Product: {product_name}. Manufacturer: {manufacturer}. Country: {country}. Date: {date}. {desc[:1000]}"

        return {
            "id": make_id("WHO-ALERT", product_name, manufacturer, str(date)),
            "source_id": "WHO-ALERT",
            "source_agency": "WHO",
            "source_type": "substandard_falsified_alert",
            "product_name": product_name,
            "manufacturer": manufacturer,
            "country_of_origin": country,
            "issue_description": str(desc)[:2000],
            "date": str(date)[:10],
            "text": text,
            "source_url": str(url),
        }
    except Exception as e:
        log.debug(f"parse_api_alert error: {e}")
        return None


def parse_alerts_html_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse WHO alerts from an HTML page."""
    records = []

    # WHO uses various article/news layouts
    items = soup.select(
        "article, "
        ".sf-news-item, "
        ".views-row, "
        ".list-item, "
        "li.sf-alert"
    )

    if not items:
        # Try generic WHO news listing
        items = soup.select(
            ".sf--item, "
            ".news-article, "
            ".item-list li"
        )

    if not items:
        # Broad fallback
        items = soup.select("div[class*='news'], div[class*='alert'], div[class*='item']")

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "h4", "a"])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if len(title) < 10:
                continue

            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""
            item_url = urljoin(WHO_BASE, link) if link and not link.startswith("http") else (link or base_url)

            date_el = (
                item.find("time") or
                item.find(attrs={"class": re.compile(r"date|time|posted", re.I)})
            )
            date = ""
            if date_el:
                date = date_el.get("datetime", date_el.get_text(strip=True))
                if date:
                    date = date[:10]

            desc_el = item.find("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            # Extract product, manufacturer, country from title/desc
            combined = title + " " + desc
            manufacturer = ""
            country = ""
            m = re.search(r"(?:manufacturer|produced by|batch)[:\s]+([^.;,\n]+)", combined, re.I)
            if m:
                manufacturer = m.group(1).strip()[:200]
            m = re.search(r"(?:country|origin)[:\s]+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)", combined, re.I)
            if m:
                country = m.group(1).strip()[:100]

            text = (
                f"WHO Substandard/Falsified Alert. Product: {title}. "
                f"Manufacturer: {manufacturer}. Country: {country}. "
                f"Date: {date}. {desc[:500]}"
            )

            records.append({
                "id": make_id("WHO-ALERT", title, manufacturer, date),
                "source_id": "WHO-ALERT",
                "source_agency": "WHO",
                "source_type": "substandard_falsified_alert",
                "product_name": title,
                "manufacturer": manufacturer,
                "country_of_origin": country,
                "issue_description": desc[:2000],
                "date": date,
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"Alert item error: {e}")
            continue

    return records


def scrape_annual_report_pdfs() -> list[dict]:
    """Scrape WHO SF annual report PDF for alert summaries."""
    records = []

    # List of known WHO SF annual report URLs to try
    report_urls = [
        "https://www.who.int/publications/i/item/WHO-MVP-EMP-SAV-2023-01",
        "https://www.who.int/publications/i/item/WHO-MVP-EMP-SAV-2022-01",
        "https://www.who.int/publications/i/item/WHO-MVP-EMP-SAV-2021-01",
        "https://www.who.int/publications/i/item/9789240052673",
    ]

    for report_url in report_urls:
        log.info(f"  Checking SF annual report: {report_url}")
        resp = get(report_url, delay=1.5, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        # Find PDF download link
        for a in soup.find_all("a", href=True):
            if a["href"].endswith(".pdf") and ("sf" in a["href"].lower() or "substandard" in a["href"].lower() or "falsif" in a["href"].lower()):
                pdf_url = urljoin(WHO_BASE, a["href"])
                time.sleep(1.5)
                pdf_resp = get(pdf_url, delay=1.5, timeout=60.0)
                if pdf_resp and len(pdf_resp.content) > 1000:
                    text = pdf_to_text(pdf_resp.content, max_pages=50)
                    if text and len(text) > 500:
                        year_m = re.search(r"\b(20\d{2})\b", pdf_url)
                        year = year_m.group(1) if year_m else ""
                        records.append({
                            "id": make_id("WHO-ALERT", "annual_report", year),
                            "source_id": "WHO-ALERT",
                            "source_agency": "WHO",
                            "source_type": "substandard_falsified_alert",
                            "product_name": f"WHO SF Annual Report {year}",
                            "manufacturer": "",
                            "country_of_origin": "",
                            "issue_description": text[:3000],
                            "date": f"{year}-01-01" if year else "",
                            "text": text[:5000],
                            "source_url": pdf_url,
                        })
                        log.info(f"    Extracted annual report PDF: {year}")
                        break

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed WHO substandard/falsified product alerts into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["product_name", "manufacturer", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    # Try API first
    log.info("Trying WHO API for SF alerts…")
    skip = 0
    while True:
        batch = fetch_api_alerts(skip=skip)
        if not batch:
            if skip == 0:
                log.info("  API returned no results")
            break
        log.info(f"  API skip={skip}: {len(batch)} records")
        for raw in batch:
            parsed = parse_api_alert(raw)
            if parsed:
                all_records.append(parsed)
        if len(batch) < 100:
            break
        skip += 100
        time.sleep(1.5)

    # HTML scraping from main pages
    html_urls = [WHO_ALERTS_LIST_URL, WHO_SF_BASE_URL]
    for url in html_urls:
        log.info(f"Scraping HTML: {url}")
        resp = get(url, delay=1.5, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        page_records = parse_alerts_html_page(soup, url)
        if page_records:
            log.info(f"  Page 1: {len(page_records)} records")
            all_records.extend(page_records)

            # Paginate
            page = 2
            while True:
                paged_url = f"{url}?page={page}"
                resp2 = get(paged_url, delay=1.5, timeout=30.0)
                if not resp2:
                    break
                soup2 = BeautifulSoup(resp2.text, "lxml")
                more = parse_alerts_html_page(soup2, paged_url)
                if not more:
                    break
                all_records.extend(more)
                log.info(f"  Page {page}: {len(more)} records")
                page += 1

    # Annual report PDFs
    log.info("Checking WHO SF annual report PDFs…")
    report_records = scrape_annual_report_pdfs()
    log.info(f"  Annual report records: {len(report_records)}")
    all_records.extend(report_records)

    new_records = []
    for r in all_records:
        key = (r.get("product_name", ""), r.get("manufacturer", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
