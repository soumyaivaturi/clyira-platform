"""
G2: ANVISA Enforcement/Recalls Seeder
=======================================
Scrapes ANVISA (Brazilian health regulatory agency) enforcement actions and recalls.
Tries RSS feed first, then HTML scraping.
Output: rag_index/anvisa_enforcement.jsonl

Usage:
    python seed_anvisa.py
    python seed_anvisa.py --dry-run
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

OUTPUT_FILE = "anvisa_enforcement.jsonl"

ANVISA_BASE = "https://www.gov.br"
ANVISA_RECALLS_URL = "https://www.gov.br/anvisa/pt-br/assuntos/fiscalizacao-e-monitoramento/recalls"
ANVISA_RSS_URL = "https://www.gov.br/anvisa/pt-br/rss.xml"
ANVISA_RECALLS_RSS = "https://www.gov.br/anvisa/pt-br/assuntos/fiscalizacao-e-monitoramento/recalls/rss.xml"
ANVISA_ALERTS_URL = "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa"
ANVISA_SAFETY_URL = "https://www.gov.br/anvisa/pt-br/assuntos/fiscalizacao-e-monitoramento/recalls"

# ANVISA API endpoints
ANVISA_API_URL = "https://www.gov.br/@anvisa/rest-api/v1/recalls"
ANVISA_SEARCH_API = "https://www.gov.br/anvisa/pt-br/@@search?SearchableText=recall&batch_size=100&b_start={start}"

# Additional fallbacks
ANVISA_RECALLS_ALT = "https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/recalls-e-alertas"
ANVISA_ENGLISH_ALT = "https://www.gov.br/anvisa/en/news"


def parse_recall_from_item(title: str, link: str, date: str, desc: str) -> dict:
    """Parse individual recall metadata."""
    # Extract company from title/desc
    company = ""
    company_patterns = [
        r"(?:empresa|fabricante|company|manufacturer)[:\s]+([^.;\n]+)",
        r"(?:M/s\.?\s+|Ltda\.?\s*|S\.A\.?\s*|Indústria\s+)([A-Z][^.;\n]{3,60})",
    ]
    for p in company_patterns:
        m = re.search(p, desc + " " + title, re.IGNORECASE)
        if m:
            company = m.group(1).strip()[:200]
            break

    # Extract product name (usually main subject of recall)
    product_name = title.strip()
    # Remove common prefixes
    for prefix in ["Recall:", "Alerta:", "Alert:", "Recolhimento:", "Cancelamento:"]:
        if product_name.lower().startswith(prefix.lower()):
            product_name = product_name[len(prefix):].strip()

    text = (
        f"ANVISA Recall/Enforcement. Product: {product_name}. "
        f"Company: {company}. Date: {date}. "
        f"Description: {desc[:500]}"
    )

    return {
        "id": make_id("ANVISA", product_name, str(date)[:10]),
        "source_id": "ANVISA",
        "source_agency": "ANVISA",
        "source_type": "recall",
        "product_name": product_name,
        "company": company,
        "reason": desc[:2000],
        "date": str(date)[:10],
        "language": "pt",
        "text": text,
        "source_url": link or ANVISA_RECALLS_URL,
    }


def scrape_rss_feed(url: str) -> list[dict]:
    """Scrape ANVISA RSS feed."""
    records = []
    log.info(f"Fetching RSS: {url}")
    resp = get(url, delay=1.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    items = soup.find_all("item")
    log.info(f"  RSS items: {len(items)}")

    for item in items:
        try:
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate") or item.find("dc:date")
            desc_el = item.find("description") or item.find("summary")

            title = title_el.get_text(strip=True) if title_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            if not link:
                link_text = item.find("link")
                link = link_text.text if link_text else ""
            date = date_el.get_text(strip=True)[:10] if date_el else ""
            desc = desc_el.get_text(strip=True) if desc_el else ""

            # Filter for recall/enforcement items
            combined = (title + " " + desc).lower()
            if not any(kw in combined for kw in
                       ["recall", "recolhimento", "alerta", "alert", "suspens", "cancel",
                        "interdição", "apreensão", "interdiç", "apreens"]):
                continue

            if not title:
                continue

            record = parse_recall_from_item(title, link, date, desc)
            records.append(record)
        except Exception as e:
            log.debug(f"RSS item error: {e}")
            continue

    return records


def scrape_api_recalls(start: int = 0) -> list[dict]:
    """Try ANVISA JSON API endpoints."""
    records = []
    api_urls = [
        f"{ANVISA_API_URL}?start={start}&limit=100",
        f"https://www.gov.br/anvisa/pt-br/@@search?portal_type=Noticia&subject=recalls&b_start={start}&b_size=100&format=json",
    ]

    for url in api_urls:
        resp = get(url, delay=1.5, timeout=30.0)
        if not resp:
            continue
        try:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                for raw in data:
                    try:
                        title = raw.get("title", raw.get("titulo", ""))
                        link = raw.get("url", raw.get("link", ""))
                        date = raw.get("date", raw.get("data", ""))
                        if isinstance(date, (int, float)):
                            date = str(int(date))
                        desc = raw.get("description", raw.get("descricao", raw.get("text", "")))
                        if not title:
                            continue
                        r = parse_recall_from_item(str(title), str(link), str(date)[:10], str(desc))
                        records.append(r)
                    except Exception:
                        continue
                return records
            if isinstance(data, dict):
                for key in ("results", "items", "data", "recalls"):
                    if key in data and isinstance(data[key], list):
                        for raw in data[key]:
                            try:
                                title = raw.get("title", raw.get("titulo", ""))
                                link = raw.get("url", raw.get("link", ""))
                                date = str(raw.get("date", raw.get("data", "")))[:10]
                                desc = raw.get("description", raw.get("descricao", ""))
                                if not title:
                                    continue
                                r = parse_recall_from_item(str(title), str(link), date, str(desc))
                                records.append(r)
                            except Exception:
                                continue
                        return records
        except Exception:
            continue

    return records


def parse_html_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Parse ANVISA HTML recall/alert listings."""
    records = []

    # Try Plone/GOV.BR content listing patterns
    items = soup.select(
        "article, "
        ".tileItem, "
        ".summary, "
        ".listing-item, "
        ".portletItem, "
        "li.tileItem"
    )

    if not items:
        items = soup.select("div[class*='item'], div[class*='result'], div[class*='news']")

    if not items:
        # Fallback to any links in main content
        main = soup.find("main") or soup.find("div", id="content") or soup
        items = [a.parent for a in main.find_all("a", href=True) if a.parent]

    seen_titles = set()
    for item in items:
        try:
            title_el = item.find(["h3", "h2", "h4", "a"])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5 or title in seen_titles:
                continue

            # Filter for recall/enforcement
            if not any(kw in title.lower() for kw in
                       ["recall", "recolhimento", "alerta", "cancel", "suspend",
                        "interdição", "apreensão", "proibição"]):
                continue

            seen_titles.add(title)
            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""
            item_url = urljoin(ANVISA_BASE, link) if link and not link.startswith("http") else (link or base_url)

            date_el = (
                item.find("time") or
                item.find(attrs={"class": re.compile(r"date|data|time", re.I)}) or
                item.find("span", string=re.compile(r"\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}"))
            )
            date = ""
            if date_el:
                date = date_el.get("datetime", date_el.get_text(strip=True))
                if date:
                    date = date[:10]

            desc_el = item.find("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            record = parse_recall_from_item(title, item_url, date, desc)
            records.append(record)
        except Exception as e:
            log.debug(f"ANVISA HTML item error: {e}")
            continue

    return records


def has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(
        soup.find("a", attrs={"rel": "next"}) or
        soup.find("a", string=re.compile(r"próxima|next|>|›", re.I)) or
        soup.find("a", attrs={"class": re.compile(r"next|forward|proximo", re.I)})
    )


def scrape_html_pages(base_url: str) -> list[dict]:
    """Scrape all pages of ANVISA recalls."""
    all_records = []

    resp = get(base_url, delay=1.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    records = parse_html_page(soup, base_url)
    if records:
        log.info(f"  Page 1: {len(records)} records")
        all_records.extend(records)

    page = 2
    while True:
        paginated_url = f"{base_url}?b_start:int={(page - 1) * 20}"
        resp2 = get(paginated_url, delay=1.5, timeout=30.0)
        if not resp2:
            break
        soup2 = BeautifulSoup(resp2.text, "lxml")
        more = parse_html_page(soup2, paginated_url)
        if not more:
            break
        all_records.extend(more)
        log.info(f"  Page {page}: {len(more)} records")
        if not has_next_page(resp2.text):
            break
        page += 1

    return all_records


def main():
    parser = argparse.ArgumentParser(description="Seed ANVISA enforcement records into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["product_name", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    # Try RSS feeds first
    for rss_url in [ANVISA_RECALLS_RSS, ANVISA_RSS_URL]:
        log.info(f"Trying RSS: {rss_url}")
        rss_records = scrape_rss_feed(rss_url)
        if rss_records:
            log.info(f"  RSS records: {len(rss_records)}")
            all_records.extend(rss_records)
            break
        time.sleep(1.5)

    # Try API
    log.info("Trying ANVISA API…")
    start = 0
    while True:
        batch = scrape_api_recalls(start=start)
        if not batch:
            if start == 0:
                log.info("  API returned no results")
            break
        log.info(f"  API start={start}: {len(batch)} records")
        all_records.extend(batch)
        if len(batch) < 100:
            break
        start += 100
        time.sleep(1.5)

    # HTML scraping fallback
    html_urls = [ANVISA_RECALLS_URL, ANVISA_RECALLS_ALT, ANVISA_ALERTS_URL]
    for url in html_urls:
        log.info(f"Scraping HTML: {url}")
        html_records = scrape_html_pages(url)
        log.info(f"  HTML records from {url}: {len(html_records)}")
        all_records.extend(html_records)
        time.sleep(1.5)

    new_records = []
    for r in all_records:
        key = (r.get("product_name", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
