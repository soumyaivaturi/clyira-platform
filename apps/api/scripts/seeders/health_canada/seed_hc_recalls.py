"""
C3: Health Canada Recalls Seeder
==================================
Scrapes Health Canada drug/health product recalls from the recalls database.
Tries JSON API first, then falls back to HTML scraping.
Paginates through all pages.
Output: rag_index/health_canada_recalls.jsonl

Usage:
    python seed_hc_recalls.py
    python seed_hc_recalls.py --dry-run
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

OUTPUT_FILE = "health_canada_recalls.jsonl"

# Health Canada recalls endpoints
# Drug category ID = 165 in the recalls/rappels system
HC_RECALLS_SEARCH_URL = "https://recalls-rappels.canada.ca/en/search/site"
HC_RECALLS_API_URL = "https://recalls-rappels.canada.ca/en/api/recall"
HC_RECALLS_JSON_API = "https://recalls-rappels.canada.ca/en/json/recall"
HC_DRUGS_PAGE = "https://www.canada.ca/en/health-canada/services/drugs-health-products/compliance-enforcement/recalls-safety-alerts.html"

DRUG_CATEGORY_IDS = ["165", "166", "134"]  # Drug, Health Products, Medical Devices


def fetch_via_api(category: str = "165", page: int = 0, per_page: int = 100) -> list[dict]:
    """Try various Health Canada recalls API endpoints."""
    api_urls = [
        f"{HC_RECALLS_API_URL}?category={category}&lang=en&page={page}&limit={per_page}",
        f"{HC_RECALLS_JSON_API}?cat={category}&lang=en&page={page}&per_page={per_page}",
        f"https://recalls-rappels.canada.ca/en/api/recalls?categories%5B%5D={category}&page={page}&limit={per_page}",
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
                for key in ("results", "data", "recalls", "items"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except Exception:
            continue

    return []


def parse_api_recall(raw: dict) -> dict | None:
    """Parse a recall from the HC API."""
    try:
        title = (
            raw.get("title") or
            raw.get("product_name") or
            raw.get("name") or
            ""
        )
        if isinstance(title, dict):
            title = title.get("en", "") or list(title.values())[0]

        product_type = raw.get("category", raw.get("product_type", raw.get("type", "")))
        if isinstance(product_type, dict):
            product_type = product_type.get("en", "") or str(product_type)
        if isinstance(product_type, list):
            product_type = ", ".join(str(x) for x in product_type)

        company = raw.get("company", raw.get("manufacturer", raw.get("firm", "")))
        if isinstance(company, dict):
            company = company.get("en", "") or str(company)

        reason = raw.get("reason", raw.get("recall_reason", raw.get("description", "")))
        if isinstance(reason, dict):
            reason = reason.get("en", "") or str(reason)

        date = (
            raw.get("date") or
            raw.get("recall_date") or
            raw.get("publish_date") or
            raw.get("year") or
            ""
        )
        if isinstance(date, (int, float)):
            date = str(int(date))

        risk_level = raw.get("risk", raw.get("risk_level", raw.get("risk_type", "")))
        if isinstance(risk_level, dict):
            risk_level = risk_level.get("en", "") or str(risk_level)

        url = raw.get("url", raw.get("link", raw.get("recall_url", "")))
        if not url:
            recall_id = raw.get("id") or raw.get("recall_id", "")
            url = f"https://recalls-rappels.canada.ca/en/alert-recall/{recall_id}" if recall_id else HC_RECALLS_SEARCH_URL

        if not title:
            return None

        text = (
            f"Health Canada Recall. Product: {title}. Company: {company}. "
            f"Type: {product_type}. Date: {date}. Risk: {risk_level}. "
            f"Reason: {reason}"
        )

        return {
            "id": make_id("HC-RECALL", title, str(date)[:10]),
            "source_id": "HC-RECALL",
            "source_agency": "Health Canada",
            "source_type": "recall",
            "title": str(title)[:500],
            "product_type": str(product_type)[:200],
            "company": str(company)[:500],
            "reason": str(reason)[:2000],
            "date": str(date)[:10],
            "risk_level": str(risk_level)[:100],
            "text": text,
            "source_url": str(url),
        }
    except Exception as e:
        log.debug(f"parse_api_recall error: {e}")
        return None


def scrape_recalls_search_page(page: int = 1, category: str = "165") -> list[dict]:
    """Scrape the HTML search results page."""
    params = urlencode({
        "f[0]": f"categories:{category}",
        "page": page - 1,  # 0-indexed
    })
    url = f"{HC_RECALLS_SEARCH_URL}?{params}"
    resp = get(url, delay=0.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    records = []

    # Find search result items
    items = soup.select(
        ".views-row, .search-result, "
        "article.node, .recall-list-item, "
        ".field-content"
    )
    if not items:
        items = soup.select("li.views-row, div.views-row")

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "a"])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""
            item_url = urljoin(HC_RECALLS_SEARCH_URL, link) if link else HC_RECALLS_SEARCH_URL

            date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
            date = date_el.get_text(strip=True) if date_el else ""

            desc_el = item.find("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            if not title:
                continue

            text = f"Health Canada Recall: {title}. {desc}. Date: {date}."
            records.append({
                "id": make_id("HC-RECALL", title, date),
                "source_id": "HC-RECALL",
                "source_agency": "Health Canada",
                "source_type": "recall",
                "title": title,
                "product_type": "Drug/Health Product",
                "company": "",
                "reason": desc,
                "date": date,
                "risk_level": "",
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"Skipping recall item: {e}")
            continue

    return records


def has_more_pages(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link:
        return True
    next_btn = soup.find("a", string=re.compile(r"next|>|›", re.I))
    return bool(next_btn)


def main():
    parser = argparse.ArgumentParser(description="Seed Health Canada recalls into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["title", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    for category_id in DRUG_CATEGORY_IDS:
        log.info(f"Fetching Health Canada recalls for category {category_id}…")

        # Try API pagination first
        api_page = 0
        api_got_results = False
        while True:
            batch = fetch_via_api(category=category_id, page=api_page, per_page=100)
            if not batch:
                if api_page == 0:
                    log.info(f"  API returned nothing for category {category_id}, trying HTML…")
                break
            api_got_results = True
            log.info(f"  API page {api_page}: {len(batch)} records")
            for raw in batch:
                parsed = parse_api_recall(raw)
                if parsed:
                    all_records.append(parsed)
            if len(batch) < 100:
                break
            api_page += 1
            time.sleep(0.5)

        if not api_got_results:
            # HTML scraping fallback
            page = 1
            while True:
                records = scrape_recalls_search_page(page=page, category=category_id)
                if not records:
                    log.info(f"  HTML page {page}: no records, stopping")
                    break
                log.info(f"  HTML page {page}: {len(records)} records")
                all_records.extend(records)

                # Check for more pages
                params = urlencode({"f[0]": f"categories:{category_id}", "page": page - 1})
                url = f"{HC_RECALLS_SEARCH_URL}?{params}"
                resp = get(url, delay=0.5, timeout=30.0)
                if not resp or not has_more_pages(resp.text):
                    break
                page += 1
                time.sleep(0.5)

    new_records = []
    for r in all_records:
        key = (r.get("title", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
