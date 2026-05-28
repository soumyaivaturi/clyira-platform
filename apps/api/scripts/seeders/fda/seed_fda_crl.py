"""
A1. FDA Complete Response Letters (openFDA API)
Fetches CRLs published via FDA's transparency initiative (July 2025+).
Output: rag_index/fda_crl.jsonl
"""
import argparse, json, logging, sys, os, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_crl.jsonl"
SOURCE_AGENCY = "FDA"
SOURCE_ID = "FDA-CRL"

# openFDA may add CRL endpoint; fall back to scraping transparency page
BASE_URL = "https://api.fda.gov/drug/other/completeresponseletters.json"
TRANSPARENCY_URL = "https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers/fda-approved-risk-evaluation-and-mitigation-strategies-rems"
CRL_INDEX_URL = "https://www.fda.gov/drugs/regulatory-processes-and-transparency/transparency-fda-drug-approval-process"

MFG_KEYWORDS = [
    "manufacturing", "facility", "cmc", "chemistry", "manufacturing and controls",
    "sterility", "validation", "process", "gmp", "good manufacturing", "inspection",
    "batch", "container closure", "stability", "analytical", "specification",
    "quality", "microbial", "endotoxin", "bioburden",
]


def is_manufacturing_related(text: str) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in MFG_KEYWORDS)


def fetch_openfda_crls(dry_run: bool) -> list[dict]:
    """Try openFDA API endpoint for CRLs."""
    records = []
    skip = 0
    limit = 100
    while True:
        url = f"{BASE_URL}?limit={limit}&skip={skip}"
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
                app_num = item.get("application_number", "")
                crl_date = item.get("date", item.get("received_date", ""))
                product = item.get("proprietary_name", item.get("product_name", ""))
                sponsor = item.get("applicant_full_name", item.get("sponsor", ""))
                deficiencies = item.get("deficiencies", item.get("issues", []))
                if isinstance(deficiencies, str):
                    deficiencies = [deficiencies]
                deficiency_text = " ".join(str(d) for d in deficiencies)
                text = (
                    f"Complete Response Letter for {product} ({app_num}). "
                    f"Sponsor: {sponsor}. Date: {crl_date}. "
                    f"Deficiencies: {deficiency_text[:1000]}"
                )
                records.append({
                    "id": make_id("CRL", app_num, crl_date),
                    "source_id": SOURCE_ID,
                    "source_agency": SOURCE_AGENCY,
                    "source_type": "complete_response_letter",
                    "application_number": app_num,
                    "application_type": item.get("application_type", ""),
                    "product_name": product,
                    "sponsor": sponsor,
                    "crl_date": crl_date,
                    "deficiency_categories": [],
                    "deficiency_text": deficiency_text[:2000],
                    "manufacturing_related": is_manufacturing_related(deficiency_text),
                    "text": text,
                    "date": crl_date,
                    "source_url": item.get("url", f"https://www.fda.gov/media/{app_num}"),
                })
            except Exception as e:
                log.debug(f"Skipping CRL record: {e}")
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += limit
        if skip >= total or len(results) < limit:
            break
    return records


def scrape_crl_index(dry_run: bool) -> list[dict]:
    """Scrape the FDA CRL transparency page as fallback."""
    from bs4 import BeautifulSoup
    records = []
    url = "https://www.fda.gov/drugs/postmarket-drug-safety-information-patients-and-providers/complete-response-letters-crl-publicly-available"
    r = get(url, delay=1.0)
    if not r:
        url = "https://www.fda.gov/about-fda/transparency/transparency-initiative"
        r = get(url, delay=1.0)
    if not r:
        log.warning("CRL index page not accessible — returning empty")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    # Look for tables or lists of CRL entries
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])] if rows else []
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            link = row.find("a")
            source_url = ""
            if link and link.get("href"):
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            try:
                # Map cells to fields by position or header
                app_num = cells[0] if len(cells) > 0 else ""
                product = cells[1] if len(cells) > 1 else ""
                sponsor = cells[2] if len(cells) > 2 else ""
                crl_date = cells[3] if len(cells) > 3 else ""
                deficiency_text = " | ".join(cells[4:]) if len(cells) > 4 else ""
                text = f"CRL for {product} ({app_num}). Sponsor: {sponsor}. Date: {crl_date}. {deficiency_text[:500]}"
                records.append({
                    "id": make_id("CRL", app_num, crl_date),
                    "source_id": SOURCE_ID,
                    "source_agency": SOURCE_AGENCY,
                    "source_type": "complete_response_letter",
                    "application_number": app_num,
                    "application_type": "",
                    "product_name": product,
                    "sponsor": sponsor,
                    "crl_date": crl_date,
                    "deficiency_categories": [],
                    "deficiency_text": deficiency_text[:2000],
                    "manufacturing_related": is_manufacturing_related(deficiency_text),
                    "text": text,
                    "date": crl_date,
                    "source_url": source_url,
                })
            except Exception as e:
                log.debug(f"Skipping row: {e}")
    log.info(f"CRL index scrape: {len(records)} records")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA Complete Response Letters")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["application_number", "crl_date"])
    log.info(f"Existing CRL records: {len(existing)}")

    # Try openFDA first, fall back to scraping
    records = fetch_openfda_crls(args.dry_run)
    if not records:
        log.info("openFDA CRL endpoint not available — trying index scrape")
        records = scrape_crl_index(args.dry_run)

    new_records = [
        r for r in records
        if (r["application_number"], r["crl_date"]) not in existing
    ]
    log.info(f"New CRL records to write: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA CRL seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
