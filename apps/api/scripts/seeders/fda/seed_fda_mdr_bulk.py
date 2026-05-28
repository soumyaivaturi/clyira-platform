"""
A15. FDA MDR Data Files (Medical Device Reports bulk download)
Downloads MDR bulk files including Alternative Summary Reports (ASR).
Output: rag_index/fda_mdr_bulk.jsonl, rag_index/fda_mdr_asr.jsonl
"""
import argparse, json, logging, sys, time, zipfile, io, csv
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_BULK = RAG_INDEX / "fda_mdr_bulk.jsonl"
OUTPUT_ASR = RAG_INDEX / "fda_mdr_asr.jsonl"

MDR_INDEX = "https://www.fda.gov/medical-devices/medical-device-reporting-mdr-how-report-medical-device-problems/mdr-data-files"
# Direct links to current year bulk files
MDR_BASE = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/detail.cfm"
MDR_BULK_BASE = "https://www.fda.gov/media/"  # actual files linked from index


def find_bulk_file_urls() -> dict:
    """Scrape the MDR data files index for download URLs."""
    r = get(MDR_INDEX, delay=0.5)
    if not r:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    urls = {}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()
        if href.endswith(".zip") or href.endswith(".txt"):
            full_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            if "foitext" in href.lower() or "foi_text" in text:
                urls["foitext"] = full_url
            elif "device" in href.lower():
                urls["device"] = full_url
            elif "patient" in href.lower():
                urls["patient"] = full_url
            elif "mdrfoi" in href.lower():
                urls["mdrfoi"] = full_url
            elif "asr" in href.lower():
                urls["asr"] = full_url
    return urls


def parse_zip_table(zip_url: str, max_records: int = 500000) -> list[dict]:
    """Download a ZIP and parse the contained delimited text file."""
    log.info(f"Downloading {zip_url}...")
    r = get(zip_url, delay=0.5, timeout=300.0)
    if not r:
        return []
    rows = []
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            for fname in zf.namelist():
                with zf.open(fname) as f:
                    content = f.read().decode("latin-1", errors="replace")
                    lines = content.splitlines()
                    if not lines:
                        continue
                    # MDR files use | delimiter
                    delimiter = "|" if "|" in lines[0] else "\t"
                    reader = csv.DictReader(lines, delimiter=delimiter)
                    for i, row in enumerate(reader):
                        if i >= max_records:
                            break
                        rows.append(dict(row))
    except Exception as e:
        log.warning(f"Failed to parse ZIP {zip_url}: {e}")
    return rows


def build_mdr_records(device_rows: list, foitext_rows: list) -> list[dict]:
    """Join device table with foitext table by MDR_REPORT_KEY."""
    # Build lookup from foitext
    text_lookup = {}
    for row in foitext_rows:
        key = row.get("MDR_REPORT_KEY", row.get("mdr_report_key", ""))
        if key:
            text_lookup[key] = row.get("FOI_TEXT", row.get("foi_text", ""))[:2000]

    records = []
    for row in device_rows:
        try:
            key = row.get("MDR_REPORT_KEY", row.get("mdr_report_key", ""))
            event_date = row.get("DATE_RECEIVED", row.get("date_received", ""))
            device_name = row.get("DEVICE_REPORT_PRODUCT_CODE", row.get("brand_name", ""))
            manufacturer = row.get("MANUFACTURER_D_NAME", row.get("manufacturer_d_name", ""))
            event_type = row.get("EVENT_TYPE", row.get("event_type", ""))
            foi_text = text_lookup.get(key, "")
            text = (
                f"MDR Report {key}: {device_name} ({manufacturer}). "
                f"Event type: {event_type}. Date: {event_date}. "
                f"{foi_text[:500]}"
            )
            records.append({
                "id": make_id("MDR", key),
                "source_id": "FDA-MDR-BULK",
                "source_agency": "FDA",
                "source_type": "mdr_report",
                "mdr_report_key": key,
                "event_date": event_date,
                "device_name": device_name,
                "manufacturer": manufacturer,
                "event_type": event_type,
                "foi_text": foi_text[:2000],
                "text": text,
                "date": event_date,
                "source_url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/detail.cfm?mdrfoi__{key}",
            })
        except Exception as e:
            log.debug(f"Skipping MDR row: {e}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA MDR bulk data files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-records", type=int, default=100000,
                        help="Max MDR records to process per file (default 100000)")
    args = parser.parse_args()

    existing_bulk = load_existing_compound_keys(OUTPUT_BULK, ["mdr_report_key"])
    existing_asr = load_existing_compound_keys(OUTPUT_ASR, ["mdr_report_key"])
    log.info(f"Existing MDR bulk: {len(existing_bulk)}, ASR: {len(existing_asr)}")

    file_urls = find_bulk_file_urls()
    log.info(f"Found MDR file URLs: {list(file_urls.keys())}")

    # Process main MDR records (device + foitext joined)
    if "device" in file_urls and "foitext" in file_urls:
        device_rows = parse_zip_table(file_urls["device"], args.max_records)
        foitext_rows = parse_zip_table(file_urls["foitext"], args.max_records)
        log.info(f"Device rows: {len(device_rows)}, FOI text rows: {len(foitext_rows)}")
        records = build_mdr_records(device_rows, foitext_rows)
        new_records = [r for r in records if (r["mdr_report_key"],) not in existing_bulk]
        log.info(f"New MDR bulk records: {len(new_records)}")
        count = append_records(OUTPUT_BULK, new_records, args.dry_run, log)
        log.info(f"MDR bulk records written: {count}")
    else:
        log.warning("MDR device/foitext bulk files not found — skipping bulk MDR")

    # Process ASR records
    if "asr" in file_urls:
        asr_rows = parse_zip_table(file_urls["asr"], args.max_records)
        asr_records = []
        for row in asr_rows:
            try:
                key = row.get("MDR_REPORT_KEY", row.get("REPORT_ID", ""))
                device = row.get("DEVICE_NAME", row.get("brand_name", ""))
                mfr = row.get("MANUFACTURER_NAME", "")
                event_type = row.get("EVENT_TYPE", "")
                date = row.get("DATE", row.get("DATE_RECEIVED", ""))
                summary = row.get("SUMMARY_REPORT_FLAG", row.get("EVENT_DESCRIPTION", ""))[:1000]
                text = f"ASR {key}: {device} ({mfr}). Event: {event_type}. Date: {date}. {summary}"
                asr_records.append({
                    "id": make_id("MDR-ASR", key),
                    "source_id": "FDA-MDR-BULK",
                    "source_agency": "FDA",
                    "source_type": "mdr_asr",
                    "mdr_report_key": key,
                    "event_date": date,
                    "device_name": device,
                    "manufacturer": mfr,
                    "event_type": event_type,
                    "foi_text": summary,
                    "text": text,
                    "date": date,
                    "source_url": MDR_INDEX,
                })
            except Exception:
                pass
        new_asr = [r for r in asr_records if (r["mdr_report_key"],) not in existing_asr]
        log.info(f"New ASR records: {len(new_asr)}")
        count2 = append_records(OUTPUT_ASR, new_asr, args.dry_run, log)
        log.info(f"MDR ASR records written: {count2}")

    log.info("FDA MDR bulk seeder complete.")


if __name__ == "__main__":
    main()
