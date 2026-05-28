"""
A5. CDER FOIA Electronic Reading Room — frequently requested compliance records.
Output: rag_index/fda_cder_foia_records.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_cder_foia_records.jsonl"

INDEX_URLS = [
    "https://www.fda.gov/drugs/cder-foia-electronic-reading-room/frequently-requested-or-proactively-posted-compliance-records",
    "https://www.fda.gov/about-fda/center-drug-evaluation-and-research-cder/cder-foia-electronic-reading-room",
]


def scrape_cder_foia() -> list[dict]:
    records = []
    seen = set()

    for base_url in INDEX_URLS:
        r = get(base_url, delay=0.4)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        # Find all PDF links with descriptive text
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if not (href.endswith(".pdf") or "/media/" in href):
                continue
            source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            if source_url in seen:
                continue
            seen.add(source_url)

            # Infer record type
            title_lower = title.lower()
            if "inspection" in title_lower or "483" in title_lower:
                record_type = "inspection_record"
            elif "warning" in title_lower:
                record_type = "warning_letter_package"
            elif "response" in title_lower:
                record_type = "compliance_response"
            else:
                record_type = "compliance_record"

            # Find company and date nearby
            parent = link.parent
            parent_text = parent.get_text(strip=True) if parent else ""
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', parent_text)
            date = date_match.group(0) if date_match else ""

            # Download PDF and extract text (skip if too slow)
            pdf_text = ""
            r2 = get(source_url, delay=0.4, timeout=45.0)
            if r2 and r2.content and len(r2.content) < 10_000_000:  # < 10MB
                pdf_text = pdf_to_text(r2.content, max_pages=15)[:2000]

            combined_text = pdf_text if pdf_text.strip() else f"CDER compliance record: {title}. Date: {date}."
            records.append({
                "id": make_id("CDER-FOIA", source_url),
                "source_id": "FDA-CDER-FOIA",
                "source_agency": "FDA/CDER",
                "source_type": record_type,
                "company": "",
                "record_type": record_type,
                "title": title,
                "date": date,
                "text": combined_text,
                "source_url": source_url,
            })
            log.debug(f"  CDER FOIA: {title[:60]}")

        # Paginate
        for page in range(2, 50):
            page_url = f"{base_url}?page={page}"
            r2 = get(page_url, delay=0.4)
            if not r2:
                break
            soup2 = BeautifulSoup(r2.text, "html.parser")
            new_links = [a for a in soup2.find_all("a", href=True)
                         if (a["href"].endswith(".pdf") or "/media/" in a["href"])
                         and a["href"] not in seen]
            if not new_links:
                break
            for link in new_links:
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                seen.add(href)
                title = link.get_text(strip=True)
                records.append({
                    "id": make_id("CDER-FOIA", source_url),
                    "source_id": "FDA-CDER-FOIA",
                    "source_agency": "FDA/CDER",
                    "source_type": "compliance_record",
                    "company": "",
                    "record_type": "compliance_record",
                    "title": title,
                    "date": "",
                    "text": f"CDER compliance record: {title}.",
                    "source_url": source_url,
                })
        log.info(f"CDER FOIA {base_url}: {len(records)} records so far")

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed CDER FOIA compliance records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["source_url"])
    log.info(f"Existing CDER FOIA records: {len(existing)}")
    records = scrape_cder_foia()
    new_records = [r for r in records if (r["source_url"],) not in existing]
    log.info(f"New CDER FOIA records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"CDER FOIA seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
