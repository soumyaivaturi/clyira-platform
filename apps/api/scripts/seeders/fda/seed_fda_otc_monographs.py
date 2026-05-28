"""
A11. FDA OTC Monographs@FDA — administrative orders and final monographs.
Output: rag_index/fda_otc_monographs.jsonl
"""
import argparse, json, logging, sys, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_otc_monographs.jsonl"

INDEX_URLS = [
    "https://www.fda.gov/drugs/over-counter-otc-drug-products/otc-monographs-fda",
    "https://www.fda.gov/drugs/over-counter-otc-drug-products/otc-drug-products-without-approved-ndas-or-andas",
]

# OTC categories
THERAPEUTIC_CATEGORIES = [
    "analgesic", "antacid", "antifungal", "antihistamine", "antipyretic",
    "antiseptic", "cough", "cold", "decongestant", "laxative",
    "sleep aid", "sunscreen", "antidiarrheal", "ophthalmic",
    "topical", "dandruff", "acne",
]

ORDER_TYPES = {
    "final": "Final Monograph",
    "proposed": "Proposed Monograph",
    "tentative": "Tentative Final Monograph",
    "advance": "Advance Notice",
    "administrative": "Administrative Order",
}


def classify_order_type(title: str) -> str:
    t = title.lower()
    for key, label in ORDER_TYPES.items():
        if key in t:
            return label
    return "OTC Monograph"


def classify_therapeutic_category(text: str) -> str:
    t = text.lower()
    for cat in THERAPEUTIC_CATEGORIES:
        if cat in t:
            return cat
    return "general"


def scrape_otc_monographs() -> list[dict]:
    records = []
    seen = set()

    for base_url in INDEX_URLS:
        r = get(base_url, delay=0.5)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        # Find monograph links in tables or lists
        for link in soup.find_all("a", href=True):
            href = link["href"]
            title = link.get_text(strip=True)

            # Look for links to monograph pages or PDFs
            if not (
                href.endswith(".pdf")
                or "/media/" in href
                or "monograph" in href.lower()
                or "administrative-order" in href.lower()
                or ("otc" in href.lower() and len(title) > 10)
            ):
                continue

            if len(title) < 5:
                continue

            source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            if source_url in seen:
                continue
            seen.add(source_url)

            # Find date nearby
            parent = link.parent
            parent_text = parent.get_text(strip=True) if parent else ""
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', parent_text)
            date = date_match.group(0) if date_match else ""

            # Extract docket number
            docket_match = re.search(r'(FDA-\d{4}-\w+-\d+|\d{4}[NP]\d{4})', title + parent_text)
            docket = docket_match.group(0) if docket_match else ""

            order_type = classify_order_type(title)
            therapeutic_cat = classify_therapeutic_category(title)

            pdf_text = ""
            if href.endswith(".pdf") or "/media/" in href:
                r2 = get(source_url, delay=0.5, timeout=60.0)
                if r2 and r2.content and len(r2.content) < 30_000_000:
                    pdf_text = pdf_to_text(r2.content)[:4000]

            combined_text = pdf_text if pdf_text.strip() else (
                f"OTC Monograph: {title}. Type: {order_type}. "
                f"Category: {therapeutic_cat}. Docket: {docket}. Date: {date}."
            )

            records.append({
                "id": make_id("OTC-MON", docket or title, date),
                "source_id": "FDA-OTC-MON",
                "source_agency": "FDA/CDER",
                "source_type": "otc_monograph",
                "title": title,
                "order_type": order_type,
                "therapeutic_category": therapeutic_cat,
                "docket_number": docket,
                "date": date,
                "text": combined_text,
                "source_url": source_url,
            })
            log.debug(f"  OTC monograph: {title[:60]}")

        # Paginate
        for page in range(2, 100):
            page_url = f"{base_url}?page={page}"
            r2 = get(page_url, delay=0.5)
            if not r2:
                break
            soup2 = BeautifulSoup(r2.text, "html.parser")
            new_links = [
                a for a in soup2.find_all("a", href=True)
                if ("monograph" in a["href"].lower() or "administrative-order" in a["href"].lower()
                    or a["href"].endswith(".pdf"))
                and len(a.get_text(strip=True)) > 5
            ]
            if not new_links:
                break
            for link in new_links:
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                if source_url in seen:
                    continue
                seen.add(source_url)
                title = link.get_text(strip=True)
                records.append({
                    "id": make_id("OTC-MON", title),
                    "source_id": "FDA-OTC-MON",
                    "source_agency": "FDA/CDER",
                    "source_type": "otc_monograph",
                    "title": title,
                    "order_type": classify_order_type(title),
                    "therapeutic_category": classify_therapeutic_category(title),
                    "docket_number": "",
                    "date": "",
                    "text": f"OTC Monograph: {title}.",
                    "source_url": source_url,
                })

        log.info(f"  {base_url}: {len(records)} OTC monograph records so far")

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA OTC Monographs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["docket_number", "title"])
    log.info(f"Existing OTC monograph records: {len(existing)}")
    records = scrape_otc_monographs()
    new_records = [r for r in records if (r["docket_number"], r["title"]) not in existing]
    log.info(f"New OTC monograph records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"OTC monographs seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
