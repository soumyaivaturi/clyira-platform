"""
D4: EDQM CEP Suspension/Withdrawal Actions Seeder
===================================================
Scrapes EDQM Certificate of Suitability (CEP) suspended/withdrawn/refused actions.
Output: rag_index/edqm_cep_actions.jsonl

Usage:
    python seed_edqm_cep.py
    python seed_edqm_cep.py --dry-run
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

OUTPUT_FILE = "edqm_cep_actions.jsonl"

EDQM_BASE = "https://www.edqm.eu"
EDQM_CEP_MAIN = "https://www.edqm.eu/en/certificate-of-suitability-cep/suspended-withdrawn-and-refused-ceps"
EDQM_CEP_ALT_1 = "https://www.edqm.eu/en/certificate_of_suitability/suspended-withdrawn-and-refused-ceps"
EDQM_CEP_ALT_2 = "https://www.edqm.eu/en/cep/suspended-withdrawn-refused"
EDQM_EXTRANET = "https://extranet.edqm.eu/publications/recherches_CEP.shtml"
EDQM_PUBLICATIONS = "https://www.edqm.eu/en/publications"


def parse_cep_action_type(text: str) -> str:
    t = text.lower()
    if "withdrawn" in t:
        return "Withdrawn"
    if "suspended" in t:
        return "Suspended"
    if "refused" in t:
        return "Refused"
    if "cancelled" in t:
        return "Cancelled"
    if "revoked" in t:
        return "Revoked"
    return "Action"


def extract_date_from_text(text: str) -> str:
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\b(\d{1,2}\s+\w+\s+\d{4})\b",
        r"\b(\w+\s+\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def parse_cep_table(soup: BeautifulSoup, base_url: str, action: str = "") -> list[dict]:
    """Parse a table of CEP actions."""
    records = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        log.debug(f"  Table headers: {headers[:8]}")

        col = {}
        for i, h in enumerate(headers):
            if "cep" in h and ("number" in h or "num" in h or "ref" in h):
                col.setdefault("cep_number", i)
            elif "holder" in h or "company" in h or "applicant" in h:
                col.setdefault("holder_name", i)
            elif "substance" in h or "active" in h or "inn" in h:
                col.setdefault("substance", i)
            elif "action" in h or "status" in h or "decision" in h:
                col.setdefault("action", i)
            elif "date" in h:
                col.setdefault("date", i)
            elif "reason" in h or "comment" in h:
                col.setdefault("reason", i)

        for row in rows[1:]:
            try:
                cols = row.find_all("td")
                if not cols:
                    continue

                def cell(key, fallback_idx=None):
                    idx = col.get(key, fallback_idx)
                    return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

                cep_number = cell("cep_number", 0)
                holder_name = cell("holder_name", 1)
                substance = cell("substance", 2)
                action_text = cell("action", 3) or action
                date = cell("date", 4)
                reason = cell("reason", 5)

                if not cep_number and not holder_name:
                    continue

                if not action_text:
                    action_text = action or parse_cep_action_type(row.get_text())

                if not date:
                    date = extract_date_from_text(row.get_text())

                link = row.find("a", href=True)
                row_url = urljoin(base_url, link["href"]) if link else base_url

                text = (
                    f"EDQM CEP {action_text}. CEP number: {cep_number}. "
                    f"Holder: {holder_name}. Substance: {substance}. "
                    f"Date: {date}. Reason: {reason}."
                )

                records.append({
                    "id": make_id("EDQM-CEP", cep_number, action_text, date),
                    "source_id": "EDQM-CEP",
                    "source_agency": "EDQM",
                    "source_type": "cep_action",
                    "cep_number": cep_number,
                    "holder_name": holder_name,
                    "substance": substance,
                    "action": action_text,
                    "date": date,
                    "text": text,
                    "source_url": row_url,
                })
            except Exception as e:
                log.debug(f"CEP table row error: {e}")
                continue

    return records


def scrape_edqm_page(url: str, action_hint: str = "") -> list[dict]:
    """Scrape an EDQM page for CEP action records."""
    resp = get(url, delay=1.5, timeout=30.0)
    if not resp:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    records = parse_cep_table(soup, url, action_hint)

    if not records:
        # Try to find links to sub-pages with suspended/withdrawn tables
        for a in soup.find_all("a", href=True):
            link_text = a.get_text(strip=True).lower()
            href = a["href"]
            if any(kw in link_text or kw in href.lower()
                   for kw in ["suspend", "withdraw", "refuse", "cancel"]):
                sub_url = urljoin(url, href)
                if sub_url != url:
                    time.sleep(1.5)
                    sub_resp = get(sub_url, delay=1.5, timeout=30.0)
                    if sub_resp:
                        sub_soup = BeautifulSoup(sub_resp.text, "lxml")
                        sub_action = parse_cep_action_type(link_text)
                        sub_records = parse_cep_table(sub_soup, sub_url, sub_action)
                        records.extend(sub_records)

    if not records:
        # Last resort: extract from page text using patterns
        page_text = soup.get_text(separator="\n")
        cep_pattern = re.compile(
            r"(R0\d{6}|CEP\s*\d{4,})\s+([A-Z][^\n]{5,80})\s+(\w[^\n]{3,50})\s+(\w+(?:ed|al))\s+(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})",
            re.IGNORECASE
        )
        for m in cep_pattern.finditer(page_text):
            try:
                cep_number = m.group(1)
                holder = m.group(2).strip()
                substance = m.group(3).strip()
                action = parse_cep_action_type(m.group(4))
                date = m.group(5)

                text = f"EDQM CEP {action}. CEP: {cep_number}. Holder: {holder}. Substance: {substance}. Date: {date}."
                records.append({
                    "id": make_id("EDQM-CEP", cep_number, action, date),
                    "source_id": "EDQM-CEP",
                    "source_agency": "EDQM",
                    "source_type": "cep_action",
                    "cep_number": cep_number,
                    "holder_name": holder,
                    "substance": substance,
                    "action": action,
                    "date": date,
                    "text": text,
                    "source_url": url,
                })
            except Exception:
                continue

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed EDQM CEP actions into RAG index")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    args = parser.parse_args()

    out_path = get_rag_index() / OUTPUT_FILE
    existing = load_existing_compound_keys(out_path, ["cep_number", "action", "date"])
    log.info(f"Existing records in {OUTPUT_FILE}: {len(existing)}")

    all_records = []

    urls_to_try = [
        (EDQM_CEP_MAIN, ""),
        (EDQM_CEP_ALT_1, ""),
        (EDQM_CEP_ALT_2, ""),
        (EDQM_EXTRANET, ""),
        (EDQM_PUBLICATIONS, ""),
    ]

    for url, action_hint in urls_to_try:
        log.info(f"Trying EDQM URL: {url}")
        records = scrape_edqm_page(url, action_hint)
        if records:
            log.info(f"  Got {len(records)} records from {url}")
            all_records.extend(records)
            break
        else:
            log.info(f"  No records found at {url}")
            time.sleep(1.5)

    if not all_records:
        log.warning("No EDQM CEP records found from any URL — check if site structure has changed")

    new_records = []
    for r in all_records:
        key = (r.get("cep_number", ""), r.get("action", ""), r.get("date", ""))
        if key not in existing:
            new_records.append(r)
            existing.add(key)

    log.info(f"New records after dedup: {len(new_records)}")
    written = append_records(out_path, new_records, args.dry_run, log)
    log.info(f"{'Would write' if args.dry_run else 'Wrote'} {written} records to {out_path}")


if __name__ == "__main__":
    main()
