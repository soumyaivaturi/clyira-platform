"""
A2. FDA Warning Letter Closeout Letters
Scrapes FDA warning letter closeout letters — showing successful remediation.
Output: rag_index/fda_closeout_letters.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_closeout_letters.jsonl"
BASE_URL = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/compliance-actions-and-activities/warning-letters"
# Warning Letters search with closeout filter
CLOSEOUT_SEARCH = "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/closeout-letters"
SEARCH_API = "https://api.fda.gov/other/warning_letters.json"


def fetch_closeout_letters() -> list[dict]:
    records = []
    # Try FDA's warning letter search API with closeout filter
    skip = 0
    limit = 100
    while True:
        url = f"{SEARCH_API}?search=closeout&limit={limit}&skip={skip}"
        r = get(url, delay=0.3)
        if not r:
            break
        try:
            data = r.json()
        except Exception:
            break
        results = data.get("results", [])
        if not results:
            break
        for item in results:
            try:
                company = item.get("company_name", "")
                issue_date = item.get("issue_date", "")
                closeout_date = item.get("closeout_date", item.get("response_date", ""))
                if not closeout_date:
                    continue  # Only process actual closeout letters
                subject = item.get("subject", "")
                office = item.get("issuing_office", "")
                text = (
                    f"FDA Warning Letter Closeout: {company}. "
                    f"Original WL: {issue_date}. Closeout: {closeout_date}. "
                    f"Office: {office}. Subject: {subject}"
                )
                records.append({
                    "id": make_id("CLOSEOUT", company, issue_date),
                    "source_id": "FDA-CLOSEOUT",
                    "source_agency": "FDA",
                    "source_type": "closeout_letter",
                    "company": company,
                    "original_wl_date": issue_date,
                    "closeout_date": closeout_date,
                    "issuing_office": office,
                    "subject": subject,
                    "text": text,
                    "date": closeout_date,
                    "source_url": item.get("url", ""),
                })
            except Exception as e:
                log.debug(f"Skipping closeout record: {e}")
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += limit
        if skip >= total or len(results) < limit:
            break
        log.info(f"  Fetched {skip} closeout letters so far...")

    if records:
        return records

    # Fallback: scrape the closeout letters index page
    log.info("API returned no closeout data — scraping index page")
    r = get(CLOSEOUT_SEARCH, delay=0.5)
    if not r:
        r = get(BASE_URL + "?filter=closeout", delay=0.5)
    if not r:
        log.warning("Closeout letters page not accessible")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    # Find all links to closeout letter detail pages
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "closeout" not in href.lower() and "close-out" not in href.lower():
            continue
        url = href if href.startswith("http") else f"https://www.fda.gov{href}"
        detail = get(url, delay=0.5)
        if not detail:
            continue
        dsoup = BeautifulSoup(detail.text, "html.parser")
        company = link.get_text(strip=True)
        date_el = dsoup.find(string=re.compile(r"\d{4}-\d{2}-\d{2}|\w+ \d+, \d{4}"))
        date_str = date_el.strip() if date_el else ""
        body_text = dsoup.get_text(separator=" ", strip=True)[:2000]
        records.append({
            "id": make_id("CLOSEOUT", company, url),
            "source_id": "FDA-CLOSEOUT",
            "source_agency": "FDA",
            "source_type": "closeout_letter",
            "company": company,
            "original_wl_date": "",
            "closeout_date": date_str,
            "issuing_office": "",
            "subject": "",
            "text": body_text,
            "date": date_str,
            "source_url": url,
        })
        log.info(f"  Closeout: {company}")

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA Warning Letter Closeout Letters")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["company", "original_wl_date"])
    log.info(f"Existing closeout records: {len(existing)}")

    records = fetch_closeout_letters()
    new_records = [
        r for r in records
        if (r["company"], r["original_wl_date"]) not in existing
    ]
    log.info(f"New closeout records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA Closeout seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
