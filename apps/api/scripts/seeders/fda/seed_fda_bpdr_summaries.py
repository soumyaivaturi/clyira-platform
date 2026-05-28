"""
A17. FDA BPDR Annual Summaries (Biological Product Deviation Reports)
Scrapes aggregate annual statistics from CBER BPDR reports.
Output: rag_index/fda_bpdr_summaries.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_bpdr_summaries.jsonl"

BPDR_INDEX_URL = "https://www.fda.gov/vaccines-blood-biologics/report-problem-center-biologics-evaluation-research/biological-product-deviation-reports-annual-summaries"

PRODUCT_CLASSES = ["blood", "plasma", "tissue", "vaccine", "hct/p", "cellular"]
DEVIATION_TYPES = [
    "manufacturing", "labeling", "storage", "shipping", "processing",
    "testing", "administration", "preparation", "collection", "pooling",
]


def extract_summary_from_text(text: str, year: str, source_url: str) -> list[dict]:
    """Parse BPDR summary text into structured deviation type records."""
    records = []
    # Extract percentage patterns: "X% of reports", "X reports", "Y% related to Z"
    patterns = [
        r'(\d+\.?\d*)\s*%\s*(?:of\s+reports\s+)?(?:were\s+)?related\s+to\s+([^\.]+)',
        r'([A-Za-z\s]+)\s+deviations?\s+accounted?\s+for\s+(\d+\.?\d*)\s*%',
        r'(\d+,?\d+)\s+reports?\s+(?:were\s+)?(?:related\s+to\s+)?([A-Za-z\s]+)',
    ]
    for pclass in PRODUCT_CLASSES:
        if pclass not in text.lower():
            continue
        # Find section for this product class
        idx = text.lower().find(pclass)
        section = text[max(0, idx-100):idx+500]
        for deviation in DEVIATION_TYPES:
            if deviation not in section.lower():
                continue
            # Try to extract count/percentage
            count_match = re.search(r'(\d+,?\d*)\s+' + deviation, section, re.I)
            pct_match = re.search(r'(\d+\.?\d*)\s*%.*' + deviation, section, re.I)
            count = count_match.group(1).replace(",", "") if count_match else "0"
            pct = pct_match.group(1) if pct_match else ""
            summary_text = (
                f"BPDR {year}: {pclass.title()} products — {deviation} deviations. "
                f"Count: {count}. {f'Percentage: {pct}%.' if pct else ''}"
            )
            records.append({
                "id": make_id("BPDR", year, pclass, deviation),
                "source_id": "FDA-BPDR-SUM",
                "source_agency": "FDA/CBER",
                "source_type": "bpdr_annual_summary",
                "year": year,
                "product_class": pclass,
                "deviation_type": deviation,
                "count": int(count) if count.isdigit() else 0,
                "total_reports": 0,
                "percentage": float(pct) if pct else 0.0,
                "trend": "",
                "text": summary_text,
                "date": f"{year}-01-01",
                "source_url": source_url,
            })
    return records


def fetch_bpdr_summaries() -> list[dict]:
    records = []
    r = get(BPDR_INDEX_URL, delay=0.4)
    if not r:
        log.warning("BPDR index not accessible")
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    # Find PDF links to annual reports
    for link in soup.find_all("a", href=True):
        href = link["href"]
        title = link.get_text(strip=True)
        if not (href.endswith(".pdf") or "annual" in title.lower() or "summary" in title.lower()):
            continue
        year_match = re.search(r'(20\d{2})', title + href)
        if not year_match:
            continue
        year = year_match.group(1)
        pdf_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
        log.info(f"  BPDR: downloading {year} summary from {pdf_url}")
        r2 = get(pdf_url, delay=0.5, timeout=60.0)
        if not r2 or not r2.content:
            continue
        text = pdf_to_text(r2.content, max_pages=30)
        if not text.strip():
            # Create a placeholder record from the page description
            page_text = soup.get_text(separator=" ", strip=True)
            year_section = re.search(
                rf'{year}.{{0,500}}deviation|deviation.{{0,200}}{year}',
                page_text, re.I | re.S
            )
            text = year_section.group(0) if year_section else f"BPDR Annual Summary {year}"

        recs = extract_summary_from_text(text, year, pdf_url)
        if not recs:
            # At minimum store a full-text record
            recs = [{
                "id": make_id("BPDR", year, "full"),
                "source_id": "FDA-BPDR-SUM",
                "source_agency": "FDA/CBER",
                "source_type": "bpdr_annual_summary",
                "year": year,
                "product_class": "all",
                "deviation_type": "all",
                "count": 0,
                "total_reports": 0,
                "percentage": 0.0,
                "trend": "",
                "text": text[:3000],
                "date": f"{year}-01-01",
                "source_url": pdf_url,
            }]
        records.extend(recs)
        log.info(f"  BPDR {year}: {len(recs)} structured records")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA BPDR Annual Summaries")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["year", "product_class", "deviation_type"])
    log.info(f"Existing BPDR records: {len(existing)}")
    records = fetch_bpdr_summaries()
    new_records = [r for r in records if (r["year"], r["product_class"], r["deviation_type"]) not in existing]
    log.info(f"New BPDR records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA BPDR seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
