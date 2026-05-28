"""
A6. Drugs@FDA — bulk application data (NDA, ANDA, BLA).
Downloads ZIP, parses application/product tables.
Output: rag_index/drugsatfda.jsonl
"""
import argparse, json, logging, sys, io, zipfile, csv
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "drugsatfda.jsonl"

BULK_ZIP_URL = "https://www.accessdata.fda.gov/drugsatfda_docs/DrugsAtFDA_Data_Files.zip"
FALLBACK_URL = "https://www.accessdata.fda.gov/drugsatfda_docs/applistall.txt"

APPROVAL_STATUSES = {"AP", "TA", "TN"}  # Approved, Tentative Approval, Not approved

ACTION_TYPES = {
    "AP": "Approved",
    "TA": "Tentatively Approved",
    "TN": "Not Approved (Tentative)",
    "WD": "Withdrawn",
}


def parse_drugs_at_fda_zip(content: bytes) -> list[dict]:
    records = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            log.info(f"  ZIP contents: {names}")

            # Load Applications table
            apps = {}
            app_file = next((n for n in names if "Application" in n and n.endswith(".txt")), None)
            if app_file:
                with zf.open(app_file) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"), delimiter="\t")
                    for row in reader:
                        appl_no = row.get("ApplNo", "").strip()
                        if appl_no:
                            apps[appl_no] = {
                                "appl_type": row.get("ApplType", "").strip(),
                                "sponsor_name": row.get("SponsorName", "").strip(),
                            }
                log.info(f"  Loaded {len(apps)} applications")

            # Load Products table
            prod_file = next((n for n in names if "Product" in n and n.endswith(".txt")), None)
            if prod_file:
                with zf.open(prod_file) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"), delimiter="\t")
                    for row in reader:
                        appl_no = row.get("ApplNo", "").strip()
                        product_no = row.get("ProductNo", "").strip()
                        drug_name = row.get("DrugName", "").strip()
                        active_ingredient = row.get("ActiveIngredient", "").strip()
                        form = row.get("Form", "").strip()
                        strength = row.get("Strength", "").strip()
                        reference_drug = row.get("ReferenceDrug", "").strip()
                        appl_info = apps.get(appl_no, {})
                        appl_type = appl_info.get("appl_type", "")
                        sponsor = appl_info.get("sponsor_name", "")
                        text = (
                            f"{appl_type} {appl_no}: {drug_name} ({active_ingredient}). "
                            f"Form: {form}. Strength: {strength}. Sponsor: {sponsor}. "
                            f"Reference listed drug: {reference_drug}."
                        )
                        records.append({
                            "id": make_id("DAFDA", appl_no, product_no),
                            "source_id": "FDA-DRUGSATFDA",
                            "source_agency": "FDA/CDER",
                            "source_type": "drug_application",
                            "application_number": f"{appl_type}{appl_no}",
                            "application_type": appl_type,
                            "product_number": product_no,
                            "drug_name": drug_name,
                            "active_ingredient": active_ingredient,
                            "form": form,
                            "strength": strength,
                            "sponsor_name": sponsor,
                            "reference_drug": reference_drug,
                            "text": text,
                            "date": "",
                            "source_url": BULK_ZIP_URL,
                        })

            # Load Submissions/actions table for approval dates
            sub_file = next((n for n in names if "Submission" in n and n.endswith(".txt")), None)
            if sub_file:
                approval_dates = {}
                with zf.open(sub_file) as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"), delimiter="\t")
                    for row in reader:
                        appl_no = row.get("ApplNo", "").strip()
                        sub_status = row.get("SubmissionStatus", "").strip()
                        action_date = row.get("SubmissionStatusDate", "").strip()
                        if sub_status in APPROVAL_STATUSES and appl_no:
                            if appl_no not in approval_dates or action_date > approval_dates[appl_no]:
                                approval_dates[appl_no] = action_date
                # Patch dates onto records
                for rec in records:
                    appl_no = rec["application_number"].replace(rec["application_type"], "").strip()
                    if appl_no in approval_dates:
                        rec["date"] = approval_dates[appl_no]
                log.info(f"  Patched approval dates for {len(approval_dates)} applications")

    except Exception as e:
        log.warning(f"Failed to parse Drugs@FDA ZIP: {e}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed Drugs@FDA application data")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["application_number", "product_number"])
    log.info(f"Existing Drugs@FDA records: {len(existing)}")

    log.info(f"Downloading Drugs@FDA bulk ZIP from {BULK_ZIP_URL}")
    r = get(BULK_ZIP_URL, delay=0.5, timeout=180.0)

    records = []
    if r and r.content and len(r.content) > 10_000:
        ct = r.headers.get("content-type", "")
        if "html" not in ct:
            records = parse_drugs_at_fda_zip(r.content)
            log.info(f"  Parsed {len(records)} product records from ZIP")
        else:
            log.warning("Got HTML instead of ZIP — trying fallback")

    if not records:
        log.info(f"Trying fallback URL: {FALLBACK_URL}")
        r2 = get(FALLBACK_URL, delay=0.5, timeout=60.0)
        if r2 and r2.text:
            for line in r2.text.splitlines():
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    appl_no = parts[0].strip()
                    drug_name = parts[1].strip() if len(parts) > 1 else ""
                    records.append({
                        "id": make_id("DAFDA", appl_no, "0"),
                        "source_id": "FDA-DRUGSATFDA",
                        "source_agency": "FDA/CDER",
                        "source_type": "drug_application",
                        "application_number": appl_no,
                        "application_type": appl_no[:3] if len(appl_no) >= 3 else "",
                        "product_number": "0",
                        "drug_name": drug_name,
                        "active_ingredient": "",
                        "form": "",
                        "strength": "",
                        "sponsor_name": "",
                        "reference_drug": "",
                        "text": f"Drug application {appl_no}: {drug_name}.",
                        "date": "",
                        "source_url": FALLBACK_URL,
                    })

    new_records = [r for r in records if (r["application_number"], r["product_number"]) not in existing]
    log.info(f"New Drugs@FDA records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"Drugs@FDA seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
