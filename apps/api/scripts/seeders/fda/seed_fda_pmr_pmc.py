"""
A8. FDA Postmarketing Requirements & Commitments (PMR/PMC)
Scrapes the PMR/PMC searchable database — flags delayed items as compliance risk.
Output: rag_index/fda_pmr_pmc.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_pmr_pmc.jsonl"

PMR_CDER_URL = "https://www.fda.gov/drugs/postmarketing-requirements-and-commitments-introduction/postmarketing-requirements-and-commitments-searchable-database"
PMR_API = "https://www.fda.gov/api/postmarketing"


def scrape_pmr_table(url: str, pmr_type: str = "PMR") -> list[dict]:
    records = []
    page = 0
    while True:
        page_url = f"{url}?page={page}" if page > 0 else url
        r = get(page_url, delay=0.4)
        if not r:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            # Try alternate structure
            rows = soup.select(".views-row, .result-row")
            if not rows:
                break
            for row in rows:
                try:
                    text_content = row.get_text(separator=" ", strip=True)
                    link = row.find("a", href=True)
                    source_url = ""
                    if link:
                        href = link["href"]
                        source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                    app_match = re.search(r'([NA][BD]A?\s*\d{6})', text_content)
                    app_num = app_match.group(1) if app_match else ""
                    status_match = re.search(r'\b(Pending|Ongoing|Delayed|Fulfilled|Released)\b', text_content, re.I)
                    status = status_match.group(1) if status_match else ""
                    records.append({
                        "id": make_id("PMR", app_num, text_content[:50]),
                        "source_id": "FDA-PMR",
                        "source_agency": "FDA",
                        "source_type": "postmarketing_requirement" if pmr_type == "PMR" else "postmarketing_commitment",
                        "application_number": app_num,
                        "product_name": "",
                        "applicant": "",
                        "requirement_description": text_content[:500],
                        "status": status,
                        "original_date": "",
                        "status_date": "",
                        "center": "CDER",
                        "text": f"{pmr_type}: {text_content[:600]}",
                        "date": "",
                        "source_url": source_url,
                    })
                except Exception as e:
                    log.debug(f"Skipping PMR row: {e}")
            # Check for next page
            next_link = soup.find("a", string=re.compile(r"next|›|»", re.I))
            if not next_link:
                break
            page += 1
            continue

        rows = table.find_all("tr")
        if not rows:
            break
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        found_in_page = 0
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if not cells or len(cells) < 2:
                continue
            try:
                def _get(idx, default=""):
                    return cells[idx].strip() if idx < len(cells) else default

                app_num = _get(0)
                product = _get(1)
                applicant = _get(2)
                req_desc = _get(3)
                status = _get(4)
                orig_date = _get(5)
                status_date = _get(6)

                link = row.find("a", href=True)
                source_url = ""
                if link:
                    href = link["href"]
                    source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"

                text = (
                    f"{pmr_type} for {product} ({app_num}). Applicant: {applicant}. "
                    f"Status: {status}. Requirement: {req_desc[:400]}. "
                    f"Original date: {orig_date}. Status date: {status_date}."
                )
                records.append({
                    "id": make_id("PMR", app_num, req_desc[:50]),
                    "source_id": "FDA-PMR",
                    "source_agency": "FDA",
                    "source_type": "postmarketing_requirement" if pmr_type == "PMR" else "postmarketing_commitment",
                    "application_number": app_num,
                    "product_name": product,
                    "applicant": applicant,
                    "requirement_description": req_desc[:1000],
                    "status": status,
                    "original_date": orig_date,
                    "status_date": status_date,
                    "center": "CDER",
                    "text": text,
                    "date": orig_date,
                    "source_url": source_url,
                })
                found_in_page += 1
            except Exception as e:
                log.debug(f"Skipping PMR table row: {e}")

        if found_in_page == 0:
            break
        next_link = soup.find("a", string=re.compile(r"next|›|»", re.I))
        if not next_link:
            break
        page += 1
        log.info(f"  PMR/PMC page {page}: {len(records)} total records")

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA PMR/PMC database")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["application_number", "requirement_description"])
    log.info(f"Existing PMR/PMC records: {len(existing)}")

    records = scrape_pmr_table(PMR_CDER_URL, "PMR")
    log.info(f"PMR/PMC records fetched: {len(records)}")

    new_records = [
        r for r in records
        if (r["application_number"], r["requirement_description"]) not in existing
    ]
    # Highlight delayed items
    delayed = sum(1 for r in new_records if "delayed" in r.get("status", "").lower())
    log.info(f"New PMR/PMC records: {len(new_records)} ({delayed} delayed)")

    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA PMR/PMC seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
