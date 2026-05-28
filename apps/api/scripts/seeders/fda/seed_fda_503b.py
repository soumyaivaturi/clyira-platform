"""
A9. FDA 503B Outsourcing Facilities — registered facilities + product reports.
Output: rag_index/fda_503b_facilities.jsonl, rag_index/fda_503b_products.jsonl
"""
import argparse, json, logging, sys, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, load_existing_compound_keys, append_records, pdf_to_text, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FAC = RAG_INDEX / "fda_503b_facilities.jsonl"
OUTPUT_PROD = RAG_INDEX / "fda_503b_products.jsonl"

FACILITIES_URL = "https://www.fda.gov/drugs/human-drug-compounding/registered-outsourcing-facilities"
PRODUCTS_URL = "https://www.fda.gov/drugs/human-drug-compounding/outsourcing-facility-reports"
ADVERSE_EVENTS_URL = "https://www.fda.gov/drugs/human-drug-compounding/503b-outsourcing-facility-adverse-event-reports"

RISK_KEYWORDS = [
    "warning letter", "483", "recall", "adverse event", "contamination",
    "sterility", "potency", "suspension", "voluntary action",
]


def scrape_facilities() -> list[dict]:
    records = []
    r = get(FACILITIES_URL, delay=0.5)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    # Try table layout first
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        headers = [th.get_text(strip=True).lower().replace(" ", "_") for th in rows[0].find_all(["th", "td"])] if rows else []
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            d = dict(zip(headers, cells)) if headers else {}
            facility_name = d.get("facility_name", d.get("name", cells[0] if cells else ""))
            city = d.get("city", cells[1] if len(cells) > 1 else "")
            state = d.get("state", cells[2] if len(cells) > 2 else "")
            country = d.get("country", cells[3] if len(cells) > 3 else "US")
            reg_date = d.get("registration_date", d.get("date_registered", ""))
            text = (
                f"503B Outsourcing Facility: {facility_name}. "
                f"Location: {city}, {state}, {country}. "
                f"Registered: {reg_date}."
            )
            records.append({
                "id": make_id("503B-FAC", facility_name, city),
                "source_id": "FDA-503B",
                "source_agency": "FDA/CDER",
                "source_type": "503b_facility",
                "facility_name": facility_name,
                "city": city,
                "state": state,
                "country": country,
                "registration_date": reg_date,
                "text": text,
                "date": reg_date,
                "source_url": FACILITIES_URL,
            })

    # Fallback: list-based layout
    if not records:
        for item in soup.select("li, .views-row, p"):
            text_content = item.get_text(strip=True)
            if len(text_content) < 10:
                continue
            # Look for patterns like "Facility Name - City, State"
            if any(c.isupper() for c in text_content[:3]):
                records.append({
                    "id": make_id("503B-FAC", text_content[:80]),
                    "source_id": "FDA-503B",
                    "source_agency": "FDA/CDER",
                    "source_type": "503b_facility",
                    "facility_name": text_content[:100],
                    "city": "",
                    "state": "",
                    "country": "US",
                    "registration_date": "",
                    "text": f"503B Outsourcing Facility: {text_content[:200]}",
                    "date": "",
                    "source_url": FACILITIES_URL,
                })

    log.info(f"  503B facilities: {len(records)}")
    return records


def scrape_product_reports() -> list[dict]:
    records = []
    seen = set()

    for url in [PRODUCTS_URL, ADVERSE_EVENTS_URL]:
        r = get(url, delay=0.5)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link["href"]
            title = link.get_text(strip=True)
            if not (href.endswith(".pdf") or "/media/" in href):
                continue
            if len(title) < 5:
                continue
            source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            if source_url in seen:
                continue
            seen.add(source_url)

            # Infer facility and date
            parent = link.parent
            parent_text = parent.get_text(strip=True) if parent else ""
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|Q[1-4]\s+\d{4}', parent_text)
            date = date_match.group(0) if date_match else ""

            # Download and parse PDF
            pdf_text = ""
            r2 = get(source_url, delay=0.5, timeout=60.0)
            if r2 and r2.content and len(r2.content) < 20_000_000:
                pdf_text = pdf_to_text(r2.content)[:3000]

            risk_flags = [kw for kw in RISK_KEYWORDS if kw in (pdf_text + title).lower()]
            combined_text = pdf_text if pdf_text.strip() else f"503B product report: {title}. Date: {date}."

            records.append({
                "id": make_id("503B-PROD", source_url),
                "source_id": "FDA-503B",
                "source_agency": "FDA/CDER",
                "source_type": "503b_product_report",
                "title": title,
                "date": date,
                "risk_flags": risk_flags,
                "has_adverse_events": "adverse_event" in title.lower() or url == ADVERSE_EVENTS_URL,
                "text": combined_text,
                "source_url": source_url,
            })
            log.debug(f"  503B product report: {title[:60]}")

        # Paginate
        for page in range(2, 50):
            page_url = f"{url}?page={page}"
            r2 = get(page_url, delay=0.5)
            if not r2:
                break
            soup2 = BeautifulSoup(r2.text, "html.parser")
            new_links = [
                a for a in soup2.find_all("a", href=True)
                if (a["href"].endswith(".pdf") or "/media/" in a["href"])
                and (a["href"] if a["href"].startswith("http") else f"https://www.fda.gov{a['href']}") not in seen
            ]
            if not new_links:
                break
            for link in new_links:
                href = link["href"]
                source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
                seen.add(source_url)
                title = link.get_text(strip=True)
                records.append({
                    "id": make_id("503B-PROD", source_url),
                    "source_id": "FDA-503B",
                    "source_agency": "FDA/CDER",
                    "source_type": "503b_product_report",
                    "title": title,
                    "date": "",
                    "risk_flags": [],
                    "has_adverse_events": url == ADVERSE_EVENTS_URL,
                    "text": f"503B product report: {title}.",
                    "source_url": source_url,
                })

        log.info(f"  {url}: {len(records)} product records so far")

    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA 503B outsourcing facilities and product reports")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing_fac = load_existing_compound_keys(OUTPUT_FAC, ["facility_name", "city"])
    existing_prod = load_existing_compound_keys(OUTPUT_PROD, ["source_url"])
    log.info(f"Existing 503B facility records: {len(existing_fac)}, product records: {len(existing_prod)}")

    facilities = scrape_facilities()
    products = scrape_product_reports()

    new_fac = [r for r in facilities if (r["facility_name"], r["city"]) not in existing_fac]
    new_prod = [r for r in products if (r["source_url"],) not in existing_prod]

    log.info(f"New 503B facilities: {len(new_fac)}, product reports: {len(new_prod)}")
    append_records(OUTPUT_FAC, new_fac, args.dry_run, log)
    append_records(OUTPUT_PROD, new_prod, args.dry_run, log)
    log.info(f"503B seeder complete. Facilities: {len(new_fac)}, Products: {len(new_prod)}")


if __name__ == "__main__":
    main()
