"""
A12. FDA REMS Dashboard
Scrapes all REMS programs — products with ETASU = elevated scrutiny.
Output: rag_index/fda_rems.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_rems.jsonl"
REMS_URL = "https://www.accessdata.fda.gov/scripts/cder/rems/index.cfm"
REMS_API = "https://api.fda.gov/drug/rems.json"


def fetch_rems_api() -> list[dict]:
    records = []
    skip = 0
    limit = 100
    while True:
        url = f"{REMS_API}?limit={limit}&skip={skip}"
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
                drug = item.get("name", "")
                app_num = item.get("application_number", "")
                has_etasu = bool(item.get("etasu", item.get("elements_to_assure_safe_use")))
                has_medguide = bool(item.get("medication_guide"))
                rems_type = "ETASU" if has_etasu else "Standard"
                approval_date = item.get("approval_date", "")
                mods = item.get("modification_dates", [])
                status = "active" if item.get("status", "").lower() not in ("released",) else "released"
                text = (
                    f"REMS Program: {drug} ({app_num}). Type: {rems_type}. "
                    f"Has ETASU: {has_etasu}. Status: {status}. "
                    f"Approval date: {approval_date}. Modifications: {len(mods)}."
                )
                records.append({
                    "id": make_id("REMS", app_num),
                    "source_id": "FDA-REMS",
                    "source_agency": "FDA",
                    "source_type": "rems_program",
                    "drug_name": drug,
                    "application_number": app_num,
                    "rems_type": rems_type,
                    "has_etasu": has_etasu,
                    "has_medication_guide": has_medguide,
                    "approval_date": approval_date,
                    "modification_dates": mods,
                    "status": status,
                    "text": text,
                    "date": approval_date,
                    "source_url": f"https://www.accessdata.fda.gov/scripts/cder/rems/index.cfm?event=IndvREMS.page&REMS={app_num}",
                })
            except Exception as e:
                log.debug(f"Skipping REMS record: {e}")
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += limit
        if skip >= total or len(results) < limit:
            break
    return records


def scrape_rems_dashboard() -> list[dict]:
    records = []
    r = get(REMS_URL, delay=0.4)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows = table.find_all("tr")
    headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th"])] if rows else []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells:
            continue
        try:
            drug = cells[0] if cells else ""
            app_num = cells[1] if len(cells) > 1 else ""
            rems_type = cells[2] if len(cells) > 2 else ""
            status = cells[3] if len(cells) > 3 else ""
            date = cells[4] if len(cells) > 4 else ""
            has_etasu = "etasu" in rems_type.lower()
            link = row.find("a", href=True)
            source_url = ""
            if link:
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.accessdata.fda.gov{href}"
            records.append({
                "id": make_id("REMS", app_num or drug, date),
                "source_id": "FDA-REMS",
                "source_agency": "FDA",
                "source_type": "rems_program",
                "drug_name": drug,
                "application_number": app_num,
                "rems_type": rems_type,
                "has_etasu": has_etasu,
                "has_medication_guide": False,
                "approval_date": date,
                "modification_dates": [],
                "status": status,
                "text": f"REMS: {drug} ({app_num}). Type: {rems_type}. Status: {status}. ETASU: {has_etasu}.",
                "date": date,
                "source_url": source_url,
            })
        except Exception as e:
            log.debug(f"Skipping REMS row: {e}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA REMS programs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["application_number"])
    log.info(f"Existing REMS records: {len(existing)}")

    records = fetch_rems_api()
    if not records:
        log.info("API returned no results — scraping REMS dashboard")
        records = scrape_rems_dashboard()

    new_records = [r for r in records if (r["application_number"],) not in existing]
    log.info(f"New REMS records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA REMS seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
