"""
B3: MHRA Drug/Device Alerts Seeder
=====================================
Scrapes MHRA drug/device alerts from GOV.UK and the Atom feed.
Paginates through all available pages.
Output: rag_index/mhra_alerts.jsonl

Usage:
    python seed_mhra_alerts.py
    python seed_mhra_alerts.py --dry-run
"""
import argparse
import json
import logging
import re
import sys
import os
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import httpx
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FILE = "mhra_alerts.jsonl"

BASE_URL = "https://www.gov.uk/drug-device-alerts"
ATOM_URL = "https://www.gov.uk/drug-device-alerts.atom"
API_URL = "https://www.gov.uk/api/content/drug-device-alerts"


def parse_alert_type(title: str, desc: str) -> str:
    text = (title + " " + desc).lower()
    if "class 1" in text or "class i recall" in text:
        return "Class 1 Recall"
    if "class 2" in text or "class ii recall" in text:
        return "Class 2 Recall"
    if "class 3" in text:
        return "Class 3 Recall"
    if "recall" in text:
        return "Recall"
    if "field safety" in text or "fsn" in text:
        return "Field Safety Notice"
    if "safety alert" in text:
        return "Safety Alert"
    if "drug alert" in text:
        return "Drug Alert"
    if "medical device" in text:
        return "Medical Device Alert"
    if "caution" in text:
        return "Caution in Use"
    return "Alert"


def extract_date_from_text(text: str) -> str:
    patterns = [
        r"\b(\d{1,2}\s+\w+\s+\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{2}/\d{2}/\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def scrape_atom_feed() -> list[dict]:
    """Fetch records from the MHRA alerts Atom feed."""
    records = []
    log.info(f"Fetching MHRA alerts Atom feed: {ATOM_URL}")
    resp = get(ATOM_URL, delay=1.0, timeout=30.0)
    if not resp:
        log.warning("Atom feed unavailable")
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    entries = soup.find_all("entry")
    log.info(f"  Atom feed entries: {len(entries)}")

    for entry in entries:
        try:
            title_el = entry.find("title")
            link_el = entry.find("link")
            updated_el = entry.find("updated")
            summary_el = entry.find("summary") or entry.find("content")

            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get("href", "") if link_el else ""
            date = updated_el.get_text(strip=True)[:10] if updated_el else ""
            description = summary_el.get_text(strip=True) if summary_el else ""

            if not title:
                continue

            alert_type = parse_alert_type(title, description)
            text = f"MHRA Alert — {alert_type}. {title}. {description}"

            records.append({
                "id": make_id("MHRA-ALERT", title, date),
                "source_id": "MHRA-ALERT",
                "source_agency": "MHRA",
                "source_type": "mhra_alert",
                "alert_type": alert_type,
                "title": title,
                "description": description,
                "alert_class": alert_type,
                "date": date,
                "text": text,
                "source_url": link or ATOM_URL,
            })
        except Exception as e:
            log.debug(f"Skipping atom entry: {e}")
            continue

    log.info(f"  Parsed {len(records)} records from Atom feed")
    return records


def scrape_alerts_page(page: int) -> list[dict]:
    """Scrape a single page of MHRA drug/device alerts."""
    url = f"{BASE_URL}?page={page}"
    resp = get(url, delay=1.0, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    records = []
    # GOV.UK search result items
    items = soup.select(
        "li.gem-c-document-list__item, "
        "div.gem-c-document-list__item, "
        "li[class*='document-list'], "
        "article.gem-c-document-list__item"
    )

    if not items:
        # Fallback: any list items with links
        items = soup.select("ul.gem-c-document-list li, .document-list li")

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "a", "span"], attrs={"class": re.compile(r"title|heading|link", re.I)})
            if not title_el:
                title_el = item.find("a", href=True)
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""

            link_full = urljoin(BASE_URL, link) if link and not link.startswith("http") else link

            # Date
            date_el = item.find(["time", "span", "p"], attrs={"class": re.compile(r"date|time|metadata", re.I)})
            date = date_el.get_text(strip=True) if date_el else ""
            if not date:
                date = extract_date_from_text(item.get_text())

            # Description
            desc_el = item.find("p", attrs={"class": re.compile(r"desc|summary|context", re.I)})
            if not desc_el:
                desc_el = item.find("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            if not title:
                continue

            alert_type = parse_alert_type(title, description)
            text = f"MHRA Alert ({alert_type}): {title}. {description}. Date: {date}."

            records.append({
                "id": make_id("MHRA-ALERT", title, date),
                "source_id": "MHRA-ALERT",
                "source_agency": "MHRA",
                "source_type": "mhra_alert",
                "alert_type": alert_type,
                "title": title,
                "description": description,
                "alert_class": alert_type,
                "date": date,
                "text": text,
                "source_url": link_full or url,
            })
        except Exception as e:
            log.debug(f"Skipping alert item: {e}")
            continue

    return records


def has_next_page(html: str) -> bool:
    """Check if the GOV.UK page has a 'next' pagination link."""
    soup = BeautifulSoup(html, "lxml")
    next_link = soup.find("a", attrs={"rel": "next"})
    if next_link:
        return True
    # Also check for Next button text
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        if text in ("next", "next page", "›", "»"):
            return True
    return False


def scrape_all_pages() -> list[dict]:
    """Paginate through all pages of MHRA alerts."""
    all_records = []
    page = 1

    while True:
        log.info(f"Scraping MHRA alerts page {page}…")
        url = f"{BASE_URL}?page={page}"
        resp = get(url, delay=1.0, timeout=30.0)
        if not resp:
            log.warning(f"No response at page {page}, stopping pagination")
            break

        page_records = scrape_alerts_page(page)
        if not page_records:
            log.info(f"  Page {page}: no records found, stopping")
            break

        log.info(f"  Page {page}: {len(page_records)} records")
        all_records.extend(page_records)

        if not has_next_page(resp.text):
            log.info(f"  No next page after page {page}")
            break

        page += 1

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed MHRA drug/device alerts into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["title", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    # Feed first (fastest), then HTML pages
    log.info("Fetching Atom feed…")
    feed_records = scrape_atom_feed()
    all_records.extend(feed_records)
    log.info(f"Feed total: {len(feed_records)}")

    log.info("Scraping paginated HTML pages…")
    page_records = scrape_all_pages()
    all_records.extend(page_records)
    log.info(f"Page scrape total: {len(page_records)}")

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
