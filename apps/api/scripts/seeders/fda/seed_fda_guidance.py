"""
A7. FDA Guidance Documents Database
Downloads GMP/quality-related FDA guidance documents (final and draft).
Output: rag_index/fda_guidance_documents.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_guidance_documents.jsonl"

# Guidance search API
GUIDANCE_SEARCH = "https://www.fda.gov/api/guidance-documents/search"
GUIDANCE_BASE = "https://www.fda.gov/regulatory-information/search-fda-guidance-documents"

# GMP/quality-related topic keywords for filtering
GMP_TOPICS = [
    "good manufacturing", "gmp", "manufacturing", "capa", "validation",
    "data integrity", "quality system", "483", "warning letter", "sterility",
    "process validation", "analytical", "stability", "computer", "part 11",
    "quality control", "cleanroom", "contamination", "aseptic", "packaging",
    "labeling", "quality agreement", "contract manufacturing", "supplier",
    "deviation", "investigation", "out-of-specification", "change control",
]

# Known high-value guidance document titles
PRIORITY_TITLES = [
    "Responding to FDA Form 483",
    "Process Validation",
    "Data Integrity",
    "CAPA",
    "Corrective and Preventive",
    "Quality Systems",
    "Current Good Manufacturing",
    "Aseptic Processing",
    "Pharmaceutical Quality",
    "ICH Q",
    "Contract Manufacturing",
    "Computer Software",
    "Electronic Records",
]


def is_quality_related(title: str, topics: list) -> bool:
    t = (title + " " + " ".join(topics or [])).lower()
    return any(kw in t for kw in GMP_TOPICS)


def fetch_guidance_list() -> list[dict]:
    """Fetch guidance document list from FDA search API."""
    records = []
    # Try JSON API
    page = 1
    while True:
        url = f"https://www.fda.gov/api/guidance-documents/search?q=manufacturing+quality+gmp&page={page}&rows=50&center=CDER,CBER,CDRH,CVM,ORA"
        r = get(url, delay=0.4)
        if not r:
            break
        try:
            data = r.json()
        except Exception:
            break
        results = data.get("results", data.get("data", []))
        if not results:
            break
        for item in results:
            try:
                title = item.get("title", item.get("name", ""))
                if not is_quality_related(title, item.get("topics", [])):
                    continue
                guid_num = item.get("guidance_number", item.get("id", ""))
                status = item.get("status", item.get("type", ""))
                date = item.get("issue_date", item.get("date", ""))
                center = item.get("center", item.get("office", ""))
                source_url = item.get("url", item.get("pdf_url", ""))
                records.append({
                    "id": make_id("GUIDANCE", guid_num or title, date),
                    "source_id": "FDA-GUIDANCE",
                    "source_agency": "FDA",
                    "source_type": "guidance_document",
                    "title": title,
                    "guidance_number": guid_num,
                    "status": status,
                    "issue_date": date,
                    "topics": item.get("topics", []),
                    "center": center,
                    "text": f"FDA Guidance: {title}. Status: {status}. Center: {center}. Date: {date}.",
                    "date": date,
                    "source_url": source_url,
                    "_pdf_url": source_url,
                })
            except Exception as e:
                log.debug(f"Skipping guidance item: {e}")
        page += 1
        if len(results) < 50:
            break
        log.info(f"  Fetched {len(records)} guidance docs so far...")
    return records


def scrape_guidance_index() -> list[dict]:
    """Fallback: scrape the guidance documents search page."""
    records = []
    for page in range(1, 200):
        url = f"{GUIDANCE_BASE}?search_api_views_fulltext=manufacturing+gmp&page={page}"
        r = get(url, delay=0.4)
        if not r:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr") or soup.select(".views-row") or soup.select("li.views-row")
        if not rows:
            break
        found = 0
        for row in rows:
            try:
                link = row.find("a", href=True)
                if not link:
                    continue
                title = link.get_text(strip=True)
                if not is_quality_related(title, []):
                    continue
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                cells = row.find_all("td")
                date = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                status = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                center = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                records.append({
                    "id": make_id("GUIDANCE", title, date),
                    "source_id": "FDA-GUIDANCE",
                    "source_agency": "FDA",
                    "source_type": "guidance_document",
                    "title": title,
                    "guidance_number": "",
                    "status": status,
                    "issue_date": date,
                    "topics": [],
                    "center": center,
                    "text": f"FDA Guidance: {title}. Status: {status}. Center: {center}. Date: {date}.",
                    "date": date,
                    "source_url": source_url,
                    "_pdf_url": source_url,
                })
                found += 1
            except Exception as e:
                log.debug(f"Skipping guidance row: {e}")
        if found == 0:
            break
        log.info(f"  Page {page}: {found} quality guidance docs")
    return records


def enrich_with_pdf_text(records: list[dict]) -> list[dict]:
    """Download PDFs and prepend extracted text to records."""
    enriched = []
    for rec in records:
        pdf_url = rec.pop("_pdf_url", "")
        if pdf_url and pdf_url.endswith(".pdf"):
            r = get(pdf_url, delay=0.5, timeout=60.0)
            if r and r.content:
                extracted = pdf_to_text(r.content, max_pages=20)
                if extracted.strip():
                    rec["text"] = extracted[:3000]
        enriched.append(rec)
    return enriched


def main():
    parser = argparse.ArgumentParser(description="Seed FDA Guidance Documents")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF text extraction")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["guidance_number", "issue_date"])
    log.info(f"Existing guidance records: {len(existing)}")

    records = fetch_guidance_list()
    if not records:
        log.info("JSON API returned no results — trying HTML scrape")
        records = scrape_guidance_index()

    new_records = [
        r for r in records
        if (r.get("guidance_number", ""), r.get("issue_date", "")) not in existing
    ]
    log.info(f"New guidance documents to process: {len(new_records)}")

    if not args.no_pdf and not args.dry_run:
        log.info("Enriching with PDF text (use --no-pdf to skip)...")
        new_records = enrich_with_pdf_text(new_records)

    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA Guidance seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
