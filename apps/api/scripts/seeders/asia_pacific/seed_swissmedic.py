"""
F3: Swissmedic Enforcement Seeder
===================================
Scrapes Swissmedic quality defects, batch recalls, and safety information
from the Swissmedic website.
Output: rag_index/swissmedic_enforcement.jsonl

Usage:
    python seed_swissmedic.py
    python seed_swissmedic.py --dry-run
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

OUTPUT_FILE = "swissmedic_enforcement.jsonl"

SWISS_BASE = "https://www.swissmedic.ch"

SWISS_QUALITY_DEFECTS_URL = (
    "https://www.swissmedic.ch/swissmedic/en/home/humanarzneimittel/"
    "marktueberwachung/qualitaetsmaengel-und-chargenrueckrufe.html"
)
SWISS_SAFETY_URL = (
    "https://www.swissmedic.ch/swissmedic/en/home/humanarzneimittel/"
    "marktuberwachung/sicherheitsinformationen.html"
)
SWISS_RECALLS_ALT = (
    "https://www.swissmedic.ch/swissmedic/en/home/humanarzneimittel/"
    "marktueberwachung/qualitaetsmaengel.html"
)
SWISS_SAFETY_ALT = (
    "https://www.swissmedic.ch/swissmedic/en/home/humanarzneimittel/"
    "marktuberwachung/sicherheitsmassnahmen.html"
)
SWISS_FIELD_SAFETY = (
    "https://www.swissmedic.ch/swissmedic/en/home/medical-devices/market-surveillance/"
    "field-safety-notices.html"
)

# Swissmedic also has an RSS/XML feed sometimes
SWISS_RSS_URL = "https://www.swissmedic.ch/swissmedic/en/home.rss"
SWISS_RECALLS_RSS = (
    "https://www.swissmedic.ch/swissmedic/en/home/humanarzneimittel/"
    "marktueberwachung/qualitaetsmaengel-und-chargenrueckrufe.rss"
)


def determine_source_type(url: str, text: str) -> str:
    combined = (url + " " + text).lower()
    if "qualit" in combined and "mangel" in combined:
        return "quality_defect"
    if "recall" in combined or "rueckruf" in combined or "chargenrueck" in combined:
        return "batch_recall"
    if "sicherheit" in combined or "safety" in combined:
        return "safety_information"
    if "field safety" in combined:
        return "field_safety_notice"
    return "enforcement"


def parse_swissmedic_table(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse Swissmedic table listings."""
    records = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        log.debug(f"  Table headers: {headers[:8]}")

        col = {}
        for i, h in enumerate(headers):
            if "product" in h or "medicine" in h or "arzneimittel" in h or "bezeichnung" in h:
                col.setdefault("product_name", i)
            elif "company" in h or "inhaber" in h or "holder" in h or "firm" in h:
                col.setdefault("company", i)
            elif "reason" in h or "grund" in h or "mangel" in h or "defect" in h:
                col.setdefault("reason", i)
            elif "date" in h or "datum" in h:
                col.setdefault("date", i)
            elif "type" in h or "art" in h or "action" in h:
                col.setdefault("type", i)
            elif "batch" in h or "charge" in h or "lot" in h:
                col.setdefault("batch", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key, fallback_idx=None):
                    idx = col.get(key, fallback_idx)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                product_name = cell("product_name", 0)
                company = cell("company", 1)
                reason = cell("reason", 2)
                date = cell("date", 3)
                source_type_hint = cell("type")

                if not product_name:
                    continue

                link = row.find("a", href=True)
                row_url = urljoin(SWISS_BASE, link["href"]) if link else base_url

                source_type = determine_source_type(base_url, source_type_hint or reason)

                text = (
                    f"Swissmedic {source_type.replace('_', ' ').title()}. "
                    f"Product: {product_name}. Company: {company}. "
                    f"Date: {date}. Reason: {reason}."
                )

                records.append({
                    "id": make_id("SWISS", product_name, date, source_type),
                    "source_id": "SWISS",
                    "source_agency": "Swissmedic",
                    "source_type": source_type,
                    "product_name": product_name,
                    "company": company,
                    "reason": reason,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"Swissmedic table row error: {e}")
                continue

    return records


def parse_swissmedic_articles(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse Swissmedic article/news item listings."""
    records = []

    items = soup.select(
        "article, .pageList__item, "
        ".newsItem, .field--item, "
        ".views-row, li.result"
    )

    if not items:
        # Try broader selector
        items = soup.select("div[class*='news'], div[class*='item'], div[class*='result']")

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "h4"])
            if not title_el:
                continue
            product_name = title_el.get_text(strip=True)
            if len(product_name) < 5:
                continue

            link = item.find("a", href=True)
            item_url = urljoin(SWISS_BASE, link["href"]) if link else base_url

            date_el = (
                item.find("time") or
                item.find(attrs={"class": re.compile(r"date|datum|time", re.I)})
            )
            date = ""
            if date_el:
                date = date_el.get("datetime", date_el.get_text(strip=True))
                if date:
                    date = date[:10]

            desc_el = item.find("p")
            reason = desc_el.get_text(strip=True) if desc_el else ""

            source_type = determine_source_type(base_url, reason or product_name)

            text = f"Swissmedic {source_type.replace('_', ' ').title()}. {product_name}. {reason}. Date: {date}."
            records.append({
                "id": make_id("SWISS", product_name, date, source_type),
                "source_id": "SWISS",
                "source_agency": "Swissmedic",
                "source_type": source_type,
                "product_name": product_name,
                "company": "",
                "reason": reason,
                "date": date,
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"Swissmedic article error: {e}")
            continue

    return records


def scrape_rss_feed(url: str) -> list[dict]:
    """Scrape Swissmedic RSS feed."""
    records = []
    resp = get(url, delay=1.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    items = soup.find_all("item")
    log.info(f"  RSS feed items: {len(items)}")

    for item in items:
        try:
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            desc_el = item.find("description")

            product_name = title_el.get_text(strip=True) if title_el else ""
            item_url = link_el.get_text(strip=True) if link_el else url
            date = date_el.get_text(strip=True)[:10] if date_el else ""
            reason = desc_el.get_text(strip=True) if desc_el else ""

            if not product_name:
                continue

            source_type = determine_source_type(item_url, reason + " " + product_name)
            text = f"Swissmedic {source_type.replace('_', ' ').title()}. {product_name}. {reason}. Date: {date}."

            records.append({
                "id": make_id("SWISS", product_name, date, source_type),
                "source_id": "SWISS",
                "source_agency": "Swissmedic",
                "source_type": source_type,
                "product_name": product_name,
                "company": "",
                "reason": reason,
                "date": date,
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"RSS item error: {e}")
            continue

    return records


def scrape_swissmedic_page_with_pagination(base_url: str) -> list[dict]:
    """Scrape a Swissmedic page with pagination support."""
    all_records = []

    resp = get(base_url, delay=1.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    records = parse_swissmedic_table(soup, base_url)
    if not records:
        records = parse_swissmedic_articles(soup, base_url)

    if records:
        log.info(f"  Page 1: {len(records)} records from {base_url}")
        all_records.extend(records)

    # Paginate
    page = 2
    while True:
        paginated_url = f"{base_url}?page={page}"
        resp2 = get(paginated_url, delay=1.5, timeout=30.0)
        if not resp2:
            break
        soup2 = BeautifulSoup(resp2.text, "lxml")
        more = parse_swissmedic_table(soup2, paginated_url)
        if not more:
            more = parse_swissmedic_articles(soup2, paginated_url)
        if not more:
            break
        all_records.extend(more)
        log.info(f"  Page {page}: {len(more)} records")
        page += 1

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed Swissmedic enforcement records into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["product_name", "date", "source_type"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    # Scrape quality defects/recalls
    quality_urls = [SWISS_QUALITY_DEFECTS_URL, SWISS_RECALLS_ALT]
    for url in quality_urls:
        log.info(f"Scraping Swissmedic quality defects: {url}")
        records = scrape_swissmedic_page_with_pagination(url)
        log.info(f"  Got {len(records)} records")
        all_records.extend(records)
        if records:
            break
        time.sleep(1.5)

    # Scrape safety information
    safety_urls = [SWISS_SAFETY_URL, SWISS_SAFETY_ALT]
    for url in safety_urls:
        log.info(f"Scraping Swissmedic safety info: {url}")
        records = scrape_swissmedic_page_with_pagination(url)
        log.info(f"  Got {len(records)} records")
        all_records.extend(records)
        if records:
            break
        time.sleep(1.5)

    # Field safety notices
    log.info(f"Scraping Swissmedic field safety notices: {SWISS_FIELD_SAFETY}")
    fsn_records = scrape_swissmedic_page_with_pagination(SWISS_FIELD_SAFETY)
    log.info(f"  Got {len(fsn_records)} field safety records")
    all_records.extend(fsn_records)

    # Try RSS feeds as supplement
    for rss_url in [SWISS_RECALLS_RSS, SWISS_RSS_URL]:
        log.info(f"Trying Swissmedic RSS: {rss_url}")
        rss_records = scrape_rss_feed(rss_url)
        log.info(f"  RSS records: {len(rss_records)}")
        all_records.extend(rss_records)

    new_records = []
    for r in all_records:
        key = (r.get("product_name", ""), r.get("date", ""), r.get("source_type", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
