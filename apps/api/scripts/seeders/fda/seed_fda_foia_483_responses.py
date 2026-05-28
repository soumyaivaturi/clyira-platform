"""
A4. FDA OII FOIA Electronic Reading Room — 483s + Firm Responses
Extracts both the 483 observation text AND the firm's response.
Output: rag_index/fda_foia_483_responses.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_foia_483_responses.jsonl"

INDEX_URLS = [
    "https://www.fda.gov/about-fda/office-inspections-and-investigations/oii-foia-electronic-reading-room",
    "https://www.fda.gov/about-fda/oii-foia-electronic-reading-room/inspectional-records-and-firm-responses",
]


def find_record_links(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract company name + 483/response PDF pairs from index page."""
    pairs = []
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            company = cells[0].get_text(strip=True)
            date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            fei = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            links = row.find_all("a", href=True)
            form483_url = ""
            response_url = ""
            for link in links:
                href = link["href"]
                link_text = link.get_text(strip=True).lower()
                full_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                if "response" in link_text or "firm" in link_text:
                    response_url = full_url
                else:
                    form483_url = full_url
            if form483_url or response_url:
                pairs.append({
                    "company": company,
                    "inspection_date": date_text,
                    "fei_number": fei,
                    "form483_url": form483_url,
                    "response_url": response_url,
                })
    # Also look for list-based layouts
    if not pairs:
        for item in soup.select("li, .views-row"):
            links = item.find_all("a", href=True)
            if len(links) < 1:
                continue
            company = item.get_text(strip=True)[:100]
            form483_url = ""
            response_url = ""
            for link in links:
                href = link["href"]
                text = link.get_text(strip=True).lower()
                full_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                if href.endswith(".pdf"):
                    if "response" in text:
                        response_url = full_url
                    else:
                        form483_url = full_url
            if form483_url or response_url:
                pairs.append({
                    "company": company,
                    "inspection_date": "",
                    "fei_number": "",
                    "form483_url": form483_url,
                    "response_url": response_url,
                })
    return pairs


def extract_pdf_pair(company: str, fei: str, date: str, form483_url: str, response_url: str) -> dict | None:
    form483_text = ""
    if form483_url:
        r = get(form483_url, delay=0.5, timeout=60.0)
        if r and r.content:
            form483_text = pdf_to_text(r.content, max_pages=30)[:3000]

    firm_response_text = ""
    if response_url:
        r = get(response_url, delay=0.5, timeout=60.0)
        if r and r.content:
            firm_response_text = pdf_to_text(r.content, max_pages=30)[:3000]

    if not form483_text and not firm_response_text:
        return None

    combined_text = f"Form 483 for {company}:\n{form483_text}\n\nFirm Response:\n{firm_response_text}"
    return {
        "id": make_id("FOIA483R", company, date),
        "source_id": "FDA-FOIA-483R",
        "source_agency": "FDA",
        "source_type": "483_firm_response",
        "company": company,
        "fei_number": fei,
        "inspection_date": date,
        "form_483_text": form483_text,
        "firm_response_text": firm_response_text,
        "text": combined_text[:4000],
        "date": date,
        "source_url": form483_url or response_url,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed FDA FOIA 483s + firm responses")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["company", "inspection_date"])
    log.info(f"Existing 483 response records: {len(existing)}")

    all_pairs = []
    for url in INDEX_URLS:
        r = get(url, delay=0.5)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        pairs = find_record_links(soup, url)
        log.info(f"  {url}: found {len(pairs)} 483/response pairs")
        all_pairs.extend(pairs)
        # Check for pagination
        for page in range(2, 100):
            page_url = f"{url}?page={page}"
            r2 = get(page_url, delay=0.4)
            if not r2:
                break
            soup2 = BeautifulSoup(r2.text, "html.parser")
            new_pairs = find_record_links(soup2, url)
            if not new_pairs:
                break
            all_pairs.extend(new_pairs)

    records = []
    for pair in all_pairs:
        if (pair["company"], pair["inspection_date"]) in existing:
            continue
        try:
            rec = extract_pdf_pair(
                pair["company"], pair["fei_number"],
                pair["inspection_date"], pair["form483_url"], pair["response_url"]
            )
            if rec:
                records.append(rec)
                log.info(f"  Extracted: {pair['company']} ({pair['inspection_date']})")
        except Exception as e:
            log.warning(f"Failed to extract PDFs for {pair['company']}: {e}")

    log.info(f"New 483 response records: {len(records)}")
    count = append_records(OUTPUT, records, args.dry_run, log)
    log.info(f"FDA FOIA 483 responses seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
