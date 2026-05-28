"""
A16. FDA CBER Safety Alerts (biologics-specific)
Output: rag_index/fda_cber_alerts.jsonl
"""
import argparse, json, logging, sys, time, re
from pathlib import Path
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
from scripts.seeders._common import get, get_rag_index, load_existing_compound_keys, append_records, make_id, RAG_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT = RAG_INDEX / "fda_cber_alerts.jsonl"

URLS = [
    "https://www.fda.gov/vaccines-blood-biologics/safety-availability-biologics",
    "https://www.fda.gov/vaccines-blood-biologics/biologics-recalls-withdrawals-safety-notifications",
    "https://www.fda.gov/vaccines-blood-biologics/safety-communications",
]
RSS_URL = "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/vaccines-blood-biologics/rss.xml"

PRODUCT_TYPES = {
    "blood": ["blood", "plasma", "platelet", "rbc", "red blood cell", "whole blood"],
    "vaccine": ["vaccine", "immunization", "shot", "flu"],
    "tissue": ["tissue", "hct/p", "cord blood", "bone", "skin", "organ"],
    "gene_therapy": ["gene therapy", "car-t", "cell therapy", "lentiviral", "adenoviral"],
    "biologic": ["biologic", "antibody", "monoclonal", "therapeutic protein", "factor"],
}


def classify_product_type(text: str) -> str:
    t = text.lower()
    for ptype, keywords in PRODUCT_TYPES.items():
        if any(kw in t for kw in keywords):
            return ptype
    return "biologic"


def scrape_cber_alerts() -> list[dict]:
    records = []
    seen = set()

    # Try RSS first
    r = get(RSS_URL, delay=0.4)
    if r:
        soup = BeautifulSoup(r.text, "xml")
        for item in soup.find_all("item"):
            try:
                title = item.find("title")
                title = title.get_text(strip=True) if title else ""
                link_el = item.find("link")
                source_url = link_el.get_text(strip=True) if link_el else ""
                pub_date = item.find("pubDate")
                date = pub_date.get_text(strip=True) if pub_date else ""
                desc = item.find("description")
                description = desc.get_text(strip=True) if desc else ""
                key = (title, date[:10])
                if key in seen:
                    continue
                seen.add(key)
                records.append({
                    "id": make_id("CBER-ALERT", title, date),
                    "source_id": "FDA-CBER-ALERT",
                    "source_agency": "FDA/CBER",
                    "source_type": "biologics_safety_alert",
                    "title": title,
                    "product_name": title,
                    "product_type": classify_product_type(title + " " + description),
                    "alert_type": "safety_communication",
                    "date": date,
                    "text": f"{title}. {description[:1000]}",
                    "source_url": source_url,
                })
            except Exception as e:
                log.debug(f"Skipping RSS item: {e}")
        log.info(f"CBER RSS: {len(records)} alerts")

    # Scrape HTML pages
    for url in URLS:
        r = get(url, delay=0.4)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"]
            title = link.get_text(strip=True)
            if len(title) < 10:
                continue
            if not any(kw in title.lower() for kw in ["recall", "alert", "safety", "notice", "warning", "withdrawal"]):
                continue
            source_url = href if href.startswith("http") else f"https://www.fda.gov{href}"
            # Find date near the link
            parent = link.parent
            date_match = re.search(r'\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}', parent.get_text())
            date = date_match.group(0) if date_match else ""
            key = (title, date[:10])
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "id": make_id("CBER-ALERT", title, date),
                "source_id": "FDA-CBER-ALERT",
                "source_agency": "FDA/CBER",
                "source_type": "biologics_safety_alert",
                "title": title,
                "product_name": title,
                "product_type": classify_product_type(title),
                "alert_type": "safety_communication",
                "date": date,
                "text": f"CBER Safety Alert: {title}. Date: {date}.",
                "source_url": source_url,
            })

    log.info(f"Total CBER alerts scraped: {len(records)}")
    return records


def main():
    parser = argparse.ArgumentParser(description="Seed FDA CBER Safety Alerts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_existing_compound_keys(OUTPUT, ["title", "date"])
    log.info(f"Existing CBER alert records: {len(existing)}")
    records = scrape_cber_alerts()
    new_records = [r for r in records if (r["title"], r["date"]) not in existing]
    log.info(f"New CBER alert records: {len(new_records)}")
    count = append_records(OUTPUT, new_records, args.dry_run, log)
    log.info(f"FDA CBER alerts seeder complete. Records written: {count}")


if __name__ == "__main__":
    main()
