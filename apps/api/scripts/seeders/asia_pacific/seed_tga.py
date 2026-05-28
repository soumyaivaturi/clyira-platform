"""
F1: TGA (Therapeutic Goods Administration) Seeder
===================================================
Scrapes TGA GMP clearance notices and safety recalls/alerts.
Paginates through all pages for both sources.
Output: rag_index/tga_gmp_notices.jsonl, rag_index/tga_recalls.jsonl

Usage:
    python seed_tga.py
    python seed_tga.py --dry-run
    python seed_tga.py --source gmp    # GMP notices only
    python seed_tga.py --source recalls  # Recalls only
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

GMP_OUTPUT_FILE = "tga_gmp_notices.jsonl"
RECALLS_OUTPUT_FILE = "tga_recalls.jsonl"

TGA_BASE = "https://www.tga.gov.au"
TGA_GMP_BASE = "https://www.tga.gov.au/news/gmp-clearance-notices"
TGA_RECALLS_BASE = "https://www.tga.gov.au/safety/recalls"
TGA_SAFETY_BASE = "https://www.tga.gov.au/safety"
TGA_GMP_ALT = "https://www.tga.gov.au/industry/manufacturing/gmp-clearance/gmp-clearance-notices"

# TGA also offers an API for recalls
TGA_RECALLS_API = "https://www.tga.gov.au/api/v1/recalls"
TGA_RECALLS_JSON = "https://www.tga.gov.au/safety/recalls.json"


def parse_action_type(text: str) -> str:
    t = text.lower()
    if "cancel" in t:
        return "Cancellation"
    if "suspend" in t:
        return "Suspension"
    if "refus" in t:
        return "Refusal"
    if "revok" in t:
        return "Revocation"
    if "approv" in t or "grant" in t:
        return "Approval"
    return "Notice"


def fetch_tga_api_recalls(page: int = 1, per_page: int = 50) -> list[dict]:
    """Try TGA recalls API endpoints."""
    api_urls = [
        f"{TGA_RECALLS_API}?page={page}&per_page={per_page}",
        f"{TGA_RECALLS_JSON}?page={page}",
        f"https://www.tga.gov.au/safety/recalls/search?page={page}&format=json",
    ]
    for url in api_urls:
        resp = get(url, delay=1.0, timeout=30.0)
        if not resp:
            continue
        try:
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("results", "data", "recalls", "items"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except Exception:
            continue
    return []


def parse_gmp_notice_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse TGA GMP clearance notice listings."""
    records = []

    # TGA lists GMP notices in tables or article cards
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        log.debug(f"  GMP table headers: {headers[:8]}")

        col = {}
        for i, h in enumerate(headers):
            if "manufacturer" in h or "company" in h or "site" in h:
                col.setdefault("manufacturer", i)
            elif "action" in h or "decision" in h or "notice" in h:
                col.setdefault("action", i)
            elif "reason" in h or "ground" in h:
                col.setdefault("reason", i)
            elif "date" in h:
                col.setdefault("date", i)
            elif "country" in h:
                col.setdefault("country", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key, fallback_idx=None):
                    idx = col.get(key, fallback_idx)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                manufacturer = cell("manufacturer", 0)
                action = cell("action", 1) or ""
                reason = cell("reason", 2) or ""
                date = cell("date", 3) or ""

                if not manufacturer:
                    continue

                if not action:
                    action = parse_action_type(reason or row.get_text())

                link = row.find("a", href=True)
                row_url = urljoin(TGA_BASE, link["href"]) if link else base_url

                text = (
                    f"TGA GMP Clearance Notice. Manufacturer: {manufacturer}. "
                    f"Action: {action}. Date: {date}. Reason: {reason}."
                )

                records.append({
                    "id": make_id("TGA-GMP", manufacturer, date),
                    "source_id": "TGA-GMP",
                    "source_agency": "TGA",
                    "source_type": "gmp_clearance_notice",
                    "manufacturer": manufacturer,
                    "action": action,
                    "reason": reason,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"GMP notice row error: {e}")
                continue

    if not records:
        # Article/card fallback
        for item in soup.select(
            "article, .views-row, "
            ".tga-search-result, "
            ".search-result, li.result"
        ):
            try:
                title_el = item.find(["h3", "h2", "h4"])
                if not title_el:
                    continue
                manufacturer = title_el.get_text(strip=True)

                link = item.find("a", href=True)
                item_url = urljoin(TGA_BASE, link["href"]) if link else base_url

                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
                date = date_el.get_text(strip=True) if date_el else ""

                desc_el = item.find("p")
                reason = desc_el.get_text(strip=True) if desc_el else ""

                action = parse_action_type(reason or manufacturer)

                if not manufacturer:
                    continue

                text = f"TGA GMP Notice. Manufacturer: {manufacturer}. Action: {action}. Date: {date}. {reason}."
                records.append({
                    "id": make_id("TGA-GMP", manufacturer, date),
                    "source_id": "TGA-GMP",
                    "source_agency": "TGA",
                    "source_type": "gmp_clearance_notice",
                    "manufacturer": manufacturer,
                    "action": action,
                    "reason": reason,
                    "date": date,
                    "text": text,
                    "source_url": item_url,
                })
            except Exception as e:
                log.debug(f"GMP item error: {e}")
                continue

    return records


def parse_recall_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse TGA recalls page."""
    records = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        col = {}
        for i, h in enumerate(headers):
            if "product" in h or "medicine" in h or "device" in h:
                col.setdefault("product_name", i)
            elif "sponsor" in h or "company" in h or "manufacturer" in h:
                col.setdefault("sponsor", i)
            elif "reason" in h or "problem" in h:
                col.setdefault("reason", i)
            elif "date" in h:
                col.setdefault("date", i)
            elif "action" in h or "class" in h:
                col.setdefault("action_class", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key, fallback_idx=None):
                    idx = col.get(key, fallback_idx)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                product_name = cell("product_name", 0)
                sponsor = cell("sponsor", 1)
                reason = cell("reason", 2)
                date = cell("date", 3)
                action_class = cell("action_class", 4)

                if not product_name:
                    continue

                link = row.find("a", href=True)
                row_url = urljoin(TGA_BASE, link["href"]) if link else base_url

                text = (
                    f"TGA Recall. Product: {product_name}. Sponsor: {sponsor}. "
                    f"Date: {date}. Reason: {reason}. Class: {action_class}."
                )

                records.append({
                    "id": make_id("TGA-RECALL", product_name, date),
                    "source_id": "TGA-RECALL",
                    "source_agency": "TGA",
                    "source_type": "recall",
                    "product_name": product_name,
                    "sponsor": sponsor,
                    "reason": reason,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Recall row error: {e}")
                continue

    if not records:
        # Article fallback
        for item in soup.select("article, .views-row, .search-result, li.result"):
            try:
                title_el = item.find(["h3", "h2", "a"])
                if not title_el:
                    continue
                product_name = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    a = item.find("a", href=True)
                    link = a["href"] if a else ""
                item_url = urljoin(TGA_BASE, link) if link and not link.startswith("http") else (link or base_url)

                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
                date = date_el.get_text(strip=True) if date_el else ""

                desc_el = item.find("p")
                reason = desc_el.get_text(strip=True) if desc_el else ""

                if not product_name:
                    continue

                text = f"TGA Recall. Product: {product_name}. Date: {date}. {reason}."
                records.append({
                    "id": make_id("TGA-RECALL", product_name, date),
                    "source_id": "TGA-RECALL",
                    "source_agency": "TGA",
                    "source_type": "recall",
                    "product_name": product_name,
                    "sponsor": "",
                    "reason": reason,
                    "date": date,
                    "text": text,
                    "source_url": item_url,
                })
            except Exception as e:
                log.debug(f"Recall item error: {e}")
                continue

    return records


def has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(
        soup.find("a", attrs={"rel": "next"}) or
        soup.find("a", string=re.compile(r"next|>|›", re.I))
    )


def scrape_all_pages(
    base_url: str, parse_fn, alt_url: str = "", delay: float = 1.0
) -> list[dict]:
    """Paginate through all pages of a TGA listing."""
    all_records = []
    active_url = base_url

    urls_to_try = [base_url]
    if alt_url:
        urls_to_try.append(alt_url)

    # Try URLs until we get results
    for try_url in urls_to_try:
        resp = get(try_url, delay=delay, timeout=30.0)
        if resp:
            soup = BeautifulSoup(resp.text, "lxml")
            records = parse_fn(soup, try_url)
            if records:
                log.info(f"  Page 1: {len(records)} records from {try_url}")
                all_records.extend(records)
                active_url = try_url
                break
            else:
                log.info(f"  No records at {try_url}")
        time.sleep(delay)

    if not all_records:
        return []

    # Paginate
    page = 2
    while True:
        paginated_url = f"{active_url}?page={page}"
        resp = get(paginated_url, delay=delay, timeout=30.0)
        if not resp:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        more = parse_fn(soup, paginated_url)
        if not more:
            log.info(f"  Page {page}: no more records")
            break
        all_records.extend(more)
        log.info(f"  Page {page}: {len(more)} records")
        if not has_next_page(resp.text):
            break
        page += 1

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed TGA GMP notices and recalls into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    parser.add_argument("--source", choices=["all", "gmp", "recalls"], default="all",
                        help="Which data source to scrape")
    args = parser.parse_args()

    gmp_out_path = get_rag_index() / GMP_OUTPUT_FILE
    recalls_out_path = get_rag_index() / RECALLS_OUTPUT_FILE

    if args.source in ("all", "gmp"):
        existing_gmp = load_existing_compound_keys(gmp_out_path, ["manufacturer", "date"])
        log.info(f"Existing GMP records: {len(existing_gmp)}")

        log.info("Scraping TGA GMP clearance notices…")
        gmp_records = scrape_all_pages(TGA_GMP_BASE, parse_gmp_notice_page, TGA_GMP_ALT, delay=1.0)
        log.info(f"Total GMP records: {len(gmp_records)}")

        new_gmp = []
        for r in gmp_records:
            key = (r.get("manufacturer", ""), r.get("date", ""))
            if key not in existing_gmp:
                new_gmp.append(r)
                existing_gmp.add(key)

        log.info(f"New GMP records after dedup: {len(new_gmp)}")
        written = append_records(gmp_out_path, new_gmp, args.dry_run, log)
        log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} GMP records to {gmp_out_path}")

    if args.source in ("all", "recalls"):
        existing_recalls = load_existing_compound_keys(recalls_out_path, ["product_name", "date"])
        log.info(f"Existing recall records: {len(existing_recalls)}")

        log.info("Scraping TGA recalls…")

        # Try API first
        api_recalls = []
        page = 1
        while True:
            batch = fetch_tga_api_recalls(page=page)
            if not batch:
                if page == 1:
                    log.info("  TGA API returned no recalls, using HTML scraping")
                break
            log.info(f"  API page {page}: {len(batch)} records")
            for raw in batch:
                # Normalize API format
                product_name = (
                    raw.get("product_name") or
                    raw.get("title") or
                    raw.get("name") or ""
                )
                sponsor = raw.get("sponsor", raw.get("company", ""))
                reason = raw.get("reason", raw.get("problem", ""))
                date = str(raw.get("date", raw.get("recall_date", "")))[:10]
                url = raw.get("url", raw.get("link", TGA_RECALLS_BASE))

                if product_name:
                    text = f"TGA Recall. Product: {product_name}. Sponsor: {sponsor}. Date: {date}. Reason: {reason}."
                    api_recalls.append({
                        "id": make_id("TGA-RECALL", product_name, date),
                        "source_id": "TGA-RECALL",
                        "source_agency": "TGA",
                        "source_type": "recall",
                        "product_name": product_name,
                        "sponsor": sponsor,
                        "reason": reason,
                        "date": date,
                        "text": text,
                        "source_url": url,
                    })
            if len(batch) < 50:
                break
            page += 1
            time.sleep(1.0)

        if api_recalls:
            recall_records = api_recalls
        else:
            recall_records = scrape_all_pages(TGA_RECALLS_BASE, parse_recall_page, "", delay=1.0)

        log.info(f"Total recall records: {len(recall_records)}")

        new_recalls = []
        for r in recall_records:
            key = (r.get("product_name", ""), r.get("date", ""))
            if key not in existing_recalls:
                new_recalls.append(r)
                existing_recalls.add(key)

        log.info(f"New recall records after dedup: {len(new_recalls)}")
        written = append_records(recalls_out_path, new_recalls, args.dry_run, log)
        log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} recall records to {recalls_out_path}")


if __name__ == "__main__":
    main()
