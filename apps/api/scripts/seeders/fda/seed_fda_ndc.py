"""
A10. FDA NDC Directory (bulk download via openFDA)
Downloads all marketed drug NDC listings.
Output: rag_index/fda_ndc_directory.jsonl
"""
import argparse, json, logging, sys, time, zipfile, io
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_ndc_directory.jsonl"

BULK_DOWNLOAD_URL = "https://open.fda.gov/apis/drug/ndc/download/"
NDC_API = "https://api.fda.gov/drug/ndc.json"
# Bulk ZIP download — much faster than API
NDC_ZIP_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"


def fetch_ndc_api() -> list[dict]:
    """Paginate through openFDA NDC API."""
    records = []
    skip = 0
    limit = 1000
    while True:
        url = f"{NDC_API}?limit={limit}&skip={skip}"
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
                ndc = item.get("product_ndc", "")
                product = item.get("brand_name", item.get("generic_name", ""))
                labeler = item.get("labeler_name", "")
                active = [
                    f"{ai.get('name', '')} {ai.get('strength', '')} {ai.get('unit', '')}"
                    for ai in item.get("active_ingredients", [])
                ]
                dosage = item.get("dosage_form", "")
                route = ", ".join(item.get("route", []))
                mktg_cat = item.get("marketing_category", "")
                mktg_start = item.get("marketing_start_date", "")
                text = (
                    f"NDC {ndc}: {product} ({labeler}). "
                    f"Active: {', '.join(active[:3])}. "
                    f"Form: {dosage}. Route: {route}. "
                    f"Category: {mktg_cat}. Marketing start: {mktg_start}."
                )
                records.append({
                    "id": make_id("NDC", ndc),
                    "source_id": "FDA-NDC",
                    "source_agency": "FDA",
                    "source_type": "ndc_listing",
                    "ndc": ndc,
                    "product_ndc": ndc,
                    "product_name": product,
                    "labeler_name": labeler,
                    "active_ingredients": active[:5],
                    "dosage_form": dosage,
                    "route": route,
                    "marketing_category": mktg_cat,
                    "marketing_start_date": mktg_start,
                    "listing_expiration_date": item.get("listing_expiration_date", ""),
                    "text": text,
                    "date": mktg_start,
                    "source_url": f"https://api.fda.gov/drug/ndc.json?search=product_ndc:{ndc}",
                })
            except Exception as e:
                log.debug(f"Skipping NDC record: {e}")

        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += limit
        if skip >= total or len(results) < limit:
            break
        if skip % 10000 == 0:
            log.info(f"  Fetched {skip}/{total} NDC records...")
    return records


def fetch_ndc_bulk() -> list[dict]:
    """Download NDC bulk ZIP and parse JSON."""
    log.info("Downloading NDC bulk ZIP...")
    r = get(NDC_ZIP_URL, delay=0.5, timeout=300.0)
    if not r:
        log.warning("NDC bulk ZIP not accessible — falling back to API")
        return []
    records = []
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for fname in zf.namelist():
                if fname.endswith(".json"):
                    with zf.open(fname) as f:
                        data = json.load(f)
                    results = data.get("results", [])
                    log.info(f"  NDC bulk: {len(results)} records in {fname}")
                    for item in results:
                        try:
                            ndc = item.get("product_ndc", "")
                            product = item.get("brand_name", item.get("generic_name", ""))
                            labeler = item.get("labeler_name", "")
                            active = [
                                f"{ai.get('name', '')} {ai.get('strength', '')}".strip()
                                for ai in item.get("active_ingredients", [])
                            ]
                            dosage = item.get("dosage_form", "")
                            route = ", ".join(item.get("route", []))
                            mktg_cat = item.get("marketing_category", "")
                            mktg_start = item.get("marketing_start_date", "")
                            text = (
                                f"NDC {ndc}: {product} ({labeler}). "
                                f"Active: {', '.join(active[:3])}. "
                                f"Form: {dosage}. Route: {route}. Category: {mktg_cat}."
                            )
                            records.append({
                                "id": make_id("NDC", ndc),
                                "source_id": "FDA-NDC",
                                "source_agency": "FDA",
                                "source_type": "ndc_listing",
                                "ndc": ndc,
                                "product_ndc": ndc,
                                "product_name": product,
                                "labeler_name": labeler,
                                "active_ingredients": active[:5],
                                "dosage_form": dosage,
                                "route": route,
                                "marketing_category": mktg_cat,
                                "marketing_start_date": mktg_start,
                                "listing_expiration_date": item.get("listing_expiration_date", ""),
                                "text": text,
                                "date": mktg_start,
                                "source_url": f"https://api.fda.gov/drug/ndc.json?search=product_ndc:{ndc}",
                            })
                        except Exception:
                            pass
    except Exception as e:
        log.warning(f"NDC bulk ZIP parse failed: {e}")
        return []
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA NDC Directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-only", action="store_true", help="Use API instead of bulk download")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["product_ndc"])
    log.info(f"Existing NDC records: {len(existing)}")

    if args.api_only:
        records = fetch_ndc_api()
    else:
        records = fetch_ndc_bulk()
        if not records:
            records = fetch_ndc_api()

    new_records = [r for r in records if (r["product_ndc"],) not in existing]
    log.info(f"New NDC records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA NDC seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
