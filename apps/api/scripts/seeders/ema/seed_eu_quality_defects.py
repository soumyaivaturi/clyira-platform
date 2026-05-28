"""
D3: EU NCA Quality Defect Alerts Seeder
==========================================
Scrapes quality defect/recall alerts from top 3 EU NCAs:
- BfArM (Germany)
- ANSM (France)
- AIFA (Italy)
Output: rag_index/eu_nca_quality_defects.jsonl

Usage:
    python seed_eu_quality_defects.py
    python seed_eu_quality_defects.py --dry-run
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

OUTPUT_FILE = "eu_nca_quality_defects.jsonl"

# ── BfArM (Germany) ──────────────────────────────────────────────────────────
BFARM_RECALLS_URL = "https://www.bfarm.de/EN/Medicinal-products/Market-surveillance/Recalls/_node.html"
BFARM_RECALLS_ALT = "https://www.bfarm.de/SharedDocs/Risikoinformationen/Rueckrufe/EN/"
BFARM_BASE = "https://www.bfarm.de"

# ── ANSM (France) ─────────────────────────────────────────────────────────────
ANSM_RECALLS_URL = "https://ansm.sante.fr/tableau-des-ruptures"
ANSM_MEASURES_URL = "https://ansm.sante.fr/nos-mesures"
ANSM_RECALLS_ALT = "https://ansm.sante.fr/actualites"
ANSM_API_URL = "https://ansm.sante.fr/api/v1/recalls"
ANSM_BASE = "https://ansm.sante.fr"

# ── AIFA (Italy) ──────────────────────────────────────────────────────────────
AIFA_RECALLS_URL = "https://www.aifa.gov.it/en/richiami-e-ritiri"
AIFA_RECALLS_ALT = "https://www.aifa.gov.it/en/recalls-and-withdrawals"
AIFA_SAFETY_URL = "https://www.aifa.gov.it/en/comunicati-stampa"
AIFA_BASE = "https://www.aifa.gov.it"


# ── BfArM scraper ─────────────────────────────────────────────────────────────

def scrape_bfarm_recalls() -> list[dict]:
    records = []
    urls_to_try = [BFARM_RECALLS_URL, BFARM_RECALLS_ALT]

    for base_url in urls_to_try:
        log.info(f"Scraping BfArM: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        page_records = _parse_bfarm_page(soup, base_url)

        if page_records:
            records.extend(page_records)
            log.info(f"  BfArM page 1: {len(page_records)} records")

        # Paginate
        page = 2
        while True:
            next_url = f"{base_url}?page={page}"
            resp2 = get(next_url, delay=1.5, timeout=30.0)
            if not resp2:
                break
            soup2 = BeautifulSoup(resp2.text, "lxml")
            more = _parse_bfarm_page(soup2, next_url)
            if not more:
                break
            records.extend(more)
            log.info(f"  BfArM page {page}: {len(more)} records")
            page += 1

        if records:
            break

    return records


def _parse_bfarm_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    records = []

    # BfArM uses various layouts — try tables first, then list items
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if len(cols) < 2:
                    continue
                product = cols[0].get_text(strip=True)
                company = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                reason = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                date = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                link = row.find("a", href=True)
                row_url = urljoin(base_url, link["href"]) if link else base_url

                if not product:
                    continue

                text = f"BfArM Quality Defect/Recall. Product: {product}. Company: {company}. Reason: {reason}. Date: {date}."
                records.append({
                    "id": make_id("EU-NCA", product, date, "Germany"),
                    "source_id": "EU-NCA",
                    "source_agency": "BfArM",
                    "source_type": "quality_defect_alert",
                    "country": "Germany",
                    "product_name": product,
                    "defect_type": reason[:200],
                    "date": date,
                    "language": "en",
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"BfArM row error: {e}")
                continue

    if not records:
        # List item fallback
        for item in soup.select("article, .recall-item, li.list-item, .field-item"):
            try:
                title_el = item.find(["h3", "h2", "a"])
                if not title_el:
                    continue
                product = title_el.get_text(strip=True)
                link = title_el.get("href", "") if title_el.name == "a" else ""
                if not link:
                    a = item.find("a", href=True)
                    link = a["href"] if a else ""
                item_url = urljoin(base_url, link) if link else base_url

                date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date", re.I)})
                date = date_el.get_text(strip=True) if date_el else ""
                desc_el = item.find("p")
                reason = desc_el.get_text(strip=True) if desc_el else ""

                if not product:
                    continue

                text = f"BfArM Quality Alert. Product: {product}. Reason: {reason}. Date: {date}."
                records.append({
                    "id": make_id("EU-NCA", product, date, "Germany"),
                    "source_id": "EU-NCA",
                    "source_agency": "BfArM",
                    "source_type": "quality_defect_alert",
                    "country": "Germany",
                    "product_name": product,
                    "defect_type": reason[:200],
                    "date": date,
                    "language": "en",
                    "text": text,
                    "source_url": item_url,
                })
            except Exception as e:
                log.debug(f"BfArM item error: {e}")
                continue

    return records


# ── ANSM scraper ──────────────────────────────────────────────────────────────

def scrape_ansm_measures() -> list[dict]:
    records = []
    urls_to_try = [ANSM_MEASURES_URL, ANSM_RECALLS_ALT, ANSM_RECALLS_URL]

    for base_url in urls_to_try:
        log.info(f"Scraping ANSM: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        page_records = _parse_ansm_page(soup, base_url)

        if page_records:
            records.extend(page_records)
            log.info(f"  ANSM page 1: {len(page_records)} records")

        # Paginate ANSM
        page = 2
        while True:
            paginated = f"{base_url}?page={page}"
            resp2 = get(paginated, delay=1.5, timeout=30.0)
            if not resp2:
                break
            soup2 = BeautifulSoup(resp2.text, "lxml")
            more = _parse_ansm_page(soup2, paginated)
            if not more:
                break
            records.extend(more)
            log.info(f"  ANSM page {page}: {len(more)} records")
            page += 1

        if records:
            break

    return records


def _parse_ansm_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    records = []
    items = soup.select(
        "article, .views-row, "
        ".field--type-ds, "
        ".node--type-actualite, "
        ".ansm-item"
    )
    if not items:
        items = soup.select("li.result, div.result, .search-result")

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "h4", "a"])
            if not title_el:
                continue
            product = title_el.get_text(strip=True)
            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""
            item_url = urljoin(ANSM_BASE, link) if link else base_url

            date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time|posted", re.I)})
            date = date_el.get_text(strip=True) if date_el else ""
            if not date:
                date_tag = item.find("time")
                date = date_tag.get("datetime", date_tag.get_text(strip=True)) if date_tag else ""

            desc_el = item.find("p")
            reason = desc_el.get_text(strip=True) if desc_el else ""

            if not product:
                continue

            text = f"ANSM Safety Measure/Recall (France). Product: {product}. {reason}. Date: {date}."
            records.append({
                "id": make_id("EU-NCA", product, date, "France"),
                "source_id": "EU-NCA",
                "source_agency": "ANSM",
                "source_type": "quality_defect_alert",
                "country": "France",
                "product_name": product,
                "defect_type": reason[:200],
                "date": date,
                "language": "fr",
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"ANSM item error: {e}")
            continue

    return records


# ── AIFA scraper ──────────────────────────────────────────────────────────────

def scrape_aifa_recalls() -> list[dict]:
    records = []
    urls_to_try = [AIFA_RECALLS_URL, AIFA_RECALLS_ALT, AIFA_SAFETY_URL]

    for base_url in urls_to_try:
        log.info(f"Scraping AIFA: {base_url}")
        resp = get(base_url, delay=1.5, timeout=30.0)
        if not resp:
            continue

        soup = BeautifulSoup(resp.text, "lxml")
        page_records = _parse_aifa_page(soup, base_url)

        if page_records:
            records.extend(page_records)
            log.info(f"  AIFA page 1: {len(page_records)} records")

        # Paginate AIFA
        page = 2
        while True:
            paginated = f"{base_url}?page={page}"
            resp2 = get(paginated, delay=1.5, timeout=30.0)
            if not resp2:
                break
            soup2 = BeautifulSoup(resp2.text, "lxml")
            more = _parse_aifa_page(soup2, paginated)
            if not more:
                break
            records.extend(more)
            log.info(f"  AIFA page {page}: {len(more)} records")
            page += 1

        if records:
            break

    return records


def _parse_aifa_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    records = []
    items = soup.select(
        "article, .views-row, "
        ".field-items > .field-item, "
        ".recall-item, .news-item"
    )
    if not items:
        # Try tables
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows[1:]:
                try:
                    cols = row.find_all("td")
                    if len(cols) < 2:
                        continue
                    product = cols[0].get_text(strip=True)
                    company = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    date = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    link = row.find("a", href=True)
                    row_url = urljoin(base_url, link["href"]) if link else base_url

                    if not product:
                        continue

                    text = f"AIFA Quality Recall/Defect (Italy). Product: {product}. Company: {company}. Date: {date}."
                    records.append({
                        "id": make_id("EU-NCA", product, date, "Italy"),
                        "source_id": "EU-NCA",
                        "source_agency": "AIFA",
                        "source_type": "quality_defect_alert",
                        "country": "Italy",
                        "product_name": product,
                        "defect_type": company,
                        "date": date,
                        "language": "it",
                        "text": text,
                        "source_url": row_url,
                    })
                except Exception as e:
                    log.debug(f"AIFA table row error: {e}")
                    continue
        return records

    for item in items:
        try:
            title_el = item.find(["h3", "h2", "h4", "a"])
            if not title_el:
                continue
            product = title_el.get_text(strip=True)
            link = title_el.get("href", "") if title_el.name == "a" else ""
            if not link:
                a = item.find("a", href=True)
                link = a["href"] if a else ""
            item_url = urljoin(AIFA_BASE, link) if link else base_url

            date_el = item.find(["time", "span"], attrs={"class": re.compile(r"date|time", re.I)})
            date = date_el.get_text(strip=True) if date_el else ""
            if not date:
                time_tag = item.find("time")
                date = time_tag.get("datetime", "") or (time_tag.get_text(strip=True) if time_tag else "")

            desc_el = item.find("p")
            reason = desc_el.get_text(strip=True) if desc_el else ""

            if not product:
                continue

            text = f"AIFA Quality Alert/Recall (Italy). Product: {product}. {reason}. Date: {date}."
            records.append({
                "id": make_id("EU-NCA", product, date, "Italy"),
                "source_id": "EU-NCA",
                "source_agency": "AIFA",
                "source_type": "quality_defect_alert",
                "country": "Italy",
                "product_name": product,
                "defect_type": reason[:200],
                "date": date,
                "language": "it",
                "text": text,
                "source_url": item_url,
            })
        except Exception as e:
            log.debug(f"AIFA item error: {e}")
            continue

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed EU NCA quality defect alerts into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    parser.add_argument("--agency", choices=["all", "bfarm", "ansm", "aifa"], default="all",
                        help="Scrape specific agency only")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["product_name", "date", "country"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    if args.agency in ("all", "bfarm"):
        log.info("Scraping BfArM (Germany)…")
        bfarm = scrape_bfarm_recalls()
        log.info(f"  BfArM total: {len(bfarm)}")
        all_records.extend(bfarm)

    if args.agency in ("all", "ansm"):
        log.info("Scraping ANSM (France)…")
        ansm = scrape_ansm_measures()
        log.info(f"  ANSM total: {len(ansm)}")
        all_records.extend(ansm)

    if args.agency in ("all", "aifa"):
        log.info("Scraping AIFA (Italy)…")
        aifa = scrape_aifa_recalls()
        log.info(f"  AIFA total: {len(aifa)}")
        all_records.extend(aifa)

    new_records = []
    for r in all_records:
        key = (r.get("product_name", ""), r.get("date", ""), r.get("country", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
