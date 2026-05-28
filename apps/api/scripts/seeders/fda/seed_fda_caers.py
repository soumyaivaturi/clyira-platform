"""
A14. FDA CAERS — Food/Supplement Adverse Events (openFDA)
Output: rag_index/fda_caers.jsonl
"""
import argparse, json, logging, sys, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_caers.jsonl"
API_URL = "https://api.fda.gov/food/event.json"


def fetch_caers() -> list[dict]:
    records = []
    skip = 0
    limit = 1000
    while True:
        url = f"{API_URL}?limit={limit}&skip={skip}"
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
                report_num = item.get("report_number", "")
                date = item.get("date_created", item.get("date_started", ""))
                products = item.get("products", [])
                product_names = [p.get("name_brand", p.get("name_english", "")) for p in products[:3]]
                outcomes = item.get("outcomes", [])
                reactions = item.get("reactions", [])
                reaction_terms = [r2.get("reaction_meddra_pt", "") for r2 in reactions[:5]]
                consumer = item.get("consumer", {})
                text = (
                    f"CAERS report {report_num}. Products: {', '.join(product_names[:3])}. "
                    f"Reactions: {', '.join(reaction_terms[:5])}. "
                    f"Outcomes: {', '.join(outcomes[:3])}. Date: {date}."
                )
                records.append({
                    "id": make_id("CAERS", report_num),
                    "source_id": "FDA-CAERS",
                    "source_agency": "FDA/CFSAN",
                    "source_type": "food_adverse_event",
                    "report_number": report_num,
                    "date_created": date,
                    "products": product_names,
                    "outcomes": outcomes[:5],
                    "reactions": reaction_terms,
                    "consumer_age": str(consumer.get("age", consumer.get("age_unit", ""))),
                    "consumer_gender": consumer.get("gender", ""),
                    "text": text,
                    "date": date,
                    "source_url": f"https://api.fda.gov/food/event.json?search=report_number:{report_num}",
                })
            except Exception as e:
                log.debug(f"Skipping CAERS record: {e}")
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += limit
        if skip >= total or len(results) < limit:
            break
        if skip % 10000 == 0:
            log.info(f"  Fetched {skip}/{total} CAERS records...")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA CAERS food adverse events")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["report_number"])
    log.info(f"Existing CAERS records: {len(existing)}")
    records = fetch_caers()
    new_records = [r for r in records if (r["report_number"],) not in existing]
    log.info(f"New CAERS records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA CAERS seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
