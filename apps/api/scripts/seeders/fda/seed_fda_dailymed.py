"""
A13. DailyMed/SPL — weekly bulk download of structured product labeling.
Very large dataset — indexed by set_id, GMP-relevant labels only.
Output: rag_index/dailymed_labels.jsonl
"""
import argparse, json, logging, sys, io, zipfile, re, xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "dailymed_labels.jsonl"

DAILYMED_API = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
BULK_INDEX_URL = "https://dailymed.nlm.nih.gov/dailymed/spl-resources-all-drug-labels.cfm"

# Only index labels with manufacturing / GMP relevance
GMP_SECTIONS = [
    "description", "how supplied", "storage and handling",
    "manufactured by", "manufactured for", "distributed by",
    "dosage forms", "sterile", "injectable", "parenteral",
    "aseptic", "reconstitution",
]

LABEL_TYPES = ["HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG", "BIOLOGICAL PRODUCT", "VACCINE"]

NS = {
    "v3": "urn:hl7-org:v3",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def extract_spl_metadata(xml_content: bytes, set_id: str, source_url: str) -> dict | None:
    """Parse SPL XML and extract GMP-relevant label fields."""
    try:
        root = ET.fromstring(xml_content)
        ns = "urn:hl7-org:v3"

        def find_text(tag_path):
            el = root.find(tag_path, {"v3": ns})
            return el.text.strip() if el is not None and el.text else ""

        # Product name
        name_el = root.find(f".//{{{ns}}}name")
        product_name = name_el.text.strip() if name_el is not None and name_el.text else ""

        # Manufacturer
        mfr_el = root.find(f".//{{{ns}}}representedOrganization/{{{ns}}}name")
        manufacturer = mfr_el.text.strip() if mfr_el is not None and mfr_el.text else ""

        # Label type
        code_el = root.find(f".//{{{ns}}}code")
        label_type = code_el.get("displayName", "") if code_el is not None else ""

        # Document date
        effective_time = root.find(f".//{{{ns}}}effectiveTime")
        date = effective_time.get("value", "") if effective_time is not None else ""
        if len(date) >= 8:
            date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"

        # Extract GMP-relevant section text
        gmp_sections_text = []
        for section in root.findall(f".//{{{ns}}}section"):
            title_el = section.find(f"{{{ns}}}title")
            title = title_el.text.strip().lower() if title_el is not None and title_el.text else ""
            if any(kw in title for kw in GMP_SECTIONS):
                text_els = section.findall(f".//{{{ns}}}text")
                section_text = " ".join(
                    ET.tostring(t, encoding="unicode", method="text").strip()
                    for t in text_els
                )[:500]
                if section_text:
                    gmp_sections_text.append(f"{title.title()}: {section_text}")

        if not product_name and not manufacturer:
            return None

        if label_type and not any(lt in label_type.upper() for lt in LABEL_TYPES):
            return None  # Skip non-drug labels

        combined_text = (
            f"SPL Label: {product_name}. Manufacturer: {manufacturer}. "
            f"Type: {label_type}. Date: {date}. "
            + " ".join(gmp_sections_text[:3])
        )[:3000]

        return {
            "id": make_id("SPL", set_id),
            "source_id": "FDA-DAILYMED",
            "source_agency": "FDA",
            "source_type": "spl_label",
            "set_id": set_id,
            "product_name": product_name,
            "manufacturer": manufacturer,
            "label_type": label_type,
            "date": date,
            "text": combined_text,
            "source_url": source_url,
        }
    except ET.ParseError as e:
        log.debug(f"XML parse error for {set_id}: {e}")
        return None
    except Exception as e:
        log.debug(f"Error parsing SPL {set_id}: {e}")
        return None


def fetch_via_api(existing: set, max_records: int = 50000) -> list[dict]:
    """Use DailyMed API to fetch label index then selectively download GMP-relevant ones."""
    records = []
    skip = 0
    page_size = 100

    log.info("Fetching DailyMed label index via API...")
    while len(records) < max_records:
        url = f"{DAILYMED_API}/spls.json?pagesize={page_size}&page={skip // page_size + 1}"
        r = get(url, delay=0.4)
        if not r:
            break
        try:
            data = r.json()
        except Exception:
            break
        items = data.get("data", [])
        if not items:
            break

        for item in items:
            set_id = item.get("setid", "")
            if not set_id or (set_id,) in existing:
                continue
            title = item.get("title", "")
            published = item.get("published", "")

            # Quick filter: skip veterinary, dietary supplements
            if "ANIMAL" in title.upper() or "SUPPLEMENT" in title.upper():
                continue

            # Fetch individual SPL XML
            spl_url = f"{DAILYMED_API}/spls/{set_id}.xml"
            r2 = get(spl_url, delay=0.4, timeout=30.0)
            if not r2 or not r2.content:
                continue
            rec = extract_spl_metadata(r2.content, set_id, f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}")
            if rec:
                rec["date"] = rec["date"] or published[:10]
                records.append(rec)

        skip += page_size
        total = data.get("metadata", {}).get("total_elements", 0)
        log.info(f"  DailyMed API: {skip}/{total} indexed, {len(records)} GMP records collected")
        if skip >= total:
            break

    return records


def fetch_via_bulk(existing: set, max_records: int = 50000) -> list[dict]:
    """Download bulk SPL ZIPs (Rx + OTC full releases), process GMP-relevant ones.

    DailyMed structure (verified 2026-05):
      Full releases: dm_spl_release_human_rx_part{1-5}.zip
                     dm_spl_release_human_otc_part{1-11}.zip
      Each outer ZIP → many inner {set_id}.zip → one {set_id}.xml
    Updates (daily/weekly/monthly) are skipped — full releases only.
    """
    records = []

    r = get(BULK_INDEX_URL, delay=0.5)
    if not r:
        return records

    soup = BeautifulSoup(r.text, "html.parser")
    all_hrefs = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".zip")]

    # Full release ZIPs for Rx and OTC — skip animal, homeopathic, and update ZIPs
    release_links = [
        h for h in all_hrefs
        if "release" in h.lower()
        and ("human_rx" in h.lower() or "human_otc" in h.lower())
        and "update" not in h.lower()
    ]
    # Deduplicate (page lists each link twice: https + ftp), prefer https
    seen_names = set()
    zip_urls = []
    for h in release_links:
        name = h.split("/")[-1]
        if name not in seen_names:
            seen_names.add(name)
            url = h if h.startswith("http") else f"https://dailymed-data.nlm.nih.gov/public-release-files/{name}"
            zip_urls.append(url)

    if not zip_urls:
        log.warning("No full-release ZIP links found on DailyMed page — check URL structure")
        return records

    log.info(f"  DailyMed: {len(zip_urls)} full-release ZIPs to process (Rx + OTC)")
    processed = 0

    for zip_url in zip_urls:
        if processed >= max_records:
            break
        log.info(f"  Downloading: {zip_url.split('/')[-1]}")
        r2 = get(zip_url, delay=0.5, timeout=600.0)
        if not r2 or not r2.content:
            log.warning(f"  Failed to download {zip_url}")
            continue

        log.info(f"  Downloaded: {len(r2.content):,} bytes")
        try:
            with zipfile.ZipFile(io.BytesIO(r2.content)) as outer_zip:
                for outer_name in outer_zip.namelist():
                    if processed >= max_records:
                        break
                    if not outer_name.endswith(".zip"):
                        continue
                    set_id = outer_name.replace(".zip", "").split("/")[-1]
                    if (set_id,) in existing:
                        continue
                    try:
                        inner_bytes = outer_zip.read(outer_name)
                        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zip:
                            xml_files = [n for n in inner_zip.namelist() if n.endswith(".xml")]
                            if not xml_files:
                                continue
                            xml_content = inner_zip.read(xml_files[0])
                            rec = extract_spl_metadata(
                                xml_content, set_id,
                                f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
                            )
                            if rec:
                                records.append(rec)
                                processed += 1
                    except Exception as e:
                        log.debug(f"  Error processing inner ZIP {set_id}: {e}")

                    if processed % 5000 == 0 and processed > 0:
                        log.info(f"  DailyMed bulk: {processed} GMP labels extracted so far")
        except Exception as e:
            log.warning(f"  Failed to process {zip_url.split('/')[-1]}: {e}")

    log.info(f"  DailyMed bulk complete: {len(records)} GMP labels")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed DailyMed/SPL structured product labeling")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-records", type=int, default=50000, help="Max records to process")
    parser.add_argument("--method", choices=["api", "bulk", "auto"], default="auto",
                        help="Fetch method: api (slow, selective), bulk (fast, needs large download), auto (try bulk first)")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["set_id"])
    log.info(f"Existing DailyMed records: {len(existing)}")

    records = []
    if args.method in ("bulk", "auto"):
        records = fetch_via_bulk(existing, args.max_records)
    if not records and args.method in ("api", "auto"):
        records = fetch_via_api(existing, args.max_records)

    new_records = [r for r in records if (r["set_id"],) not in existing]
    log.info(f"New DailyMed SPL records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"DailyMed seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
