"""
FDA Import Alerts Seeder
========================
Scrapes the FDA Import Alert list at accessdata.fda.gov/cms_ia/ialist.html,
follows each alert's detail page, and writes rag_index/import_alerts.jsonl.

Fields: alert_number, alert_type (DWPE/detention), country, product, charges,
        cfr_citations, firms_on_list, source_url.

Usage:
    cd apps/api
    python scripts/seed_import_alerts.py
    python scripts/seed_import_alerts.py --dry-run
"""
import asyncio
import argparse
import json
import logging
import re
import sys
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_import_alerts")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "import_alerts.jsonl"

IA_LIST_URL = "https://www.accessdata.fda.gov/cms_ia/ialist.html"
IA_BASE = "https://www.accessdata.fda.gov"

CFR_PATTERN = re.compile(
    r'21\s+CFR\s+(?:§§?\s*)?[\d.]+(?:\([a-z0-9]+\))*',
    re.IGNORECASE,
)


def _extract_cfr(text: str) -> list[str]:
    raw = CFR_PATTERN.findall(text)
    return list(dict.fromkeys(c.rstrip("(").strip() for c in raw if c))


def _alert_type_from_text(text: str) -> str:
    tl = text.lower()
    if "detention without physical examination" in tl or "dwpe" in tl:
        return "DWPE"
    if "automatic detention" in tl:
        return "automatic_detention"
    if "surveillance" in tl:
        return "surveillance"
    return "detention"


async def fetch_alert_detail(client: httpx.AsyncClient, url: str) -> dict:
    """Scrape an individual import alert detail page."""
    try:
        resp = await client.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        log.debug(f"Alert detail fetch failed ({url}): {e}")
        return {}

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    # Extract country (common label)
    country = ""
    m = re.search(r"(?:Country|Countries?)[\s:]+([A-Za-z ,]+?)(?:\n|\.|\s{3})", text)
    if m:
        country = m.group(1).strip()[:200]

    # Extract product description
    product = ""
    m = re.search(r"(?:Product|Article|Commodity)[\s:]+(.{10,200}?)(?:\n|\.)", text)
    if m:
        product = m.group(1).strip()

    # Extract charge/reason
    charges = ""
    m = re.search(r"(?:Charges?|Reason|Grounds?)[\s:]+(.{20,500}?)(?:\n\n|\Z)", text, re.DOTALL)
    if m:
        charges = re.sub(r"\s+", " ", m.group(1)).strip()[:1000]

    # Extract firms on list
    firms: list[str] = []
    # Look for a "Firms Subject to This Alert" section
    firms_section = re.search(
        r"(?:firms?\s+subject|red list|entities?\s+subject)[:\s]+(.{0,3000}?)(?=\n\n|\Z)",
        text, re.IGNORECASE | re.DOTALL
    )
    if firms_section:
        firm_text = firms_section.group(1)
        # Split on newlines or numbered items
        for line in re.split(r"\n|\d+\.\s+", firm_text):
            line = line.strip()
            if 5 < len(line) < 200:
                firms.append(line)
    firms = firms[:100]  # cap at 100 firm names per alert

    return {
        "country": country[:200],
        "product": product[:500],
        "charges": charges,
        "cfr_citations": _extract_cfr(text),
        "alert_type": _alert_type_from_text(text),
        "firms_on_list": firms,
        "full_text_excerpt": text[:1000],
    }


async def scrape_alert_list(client: httpx.AsyncClient) -> list[tuple[str, str, str]]:
    """
    Scrape the import alert list page and all pagination.
    Returns list of (alert_number, alert_title, detail_url).
    """
    results: list[tuple[str, str, str]] = []
    page_url: Optional[str] = IA_LIST_URL

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.warning(f"Import alert list fetch failed ({page_url}): {e}")
            break

        # The list page has rows with alert number + title + link
        rows = soup.select("table tr, .views-row")
        for row in rows:
            try:
                cols = row.find_all("td")
                if not cols:
                    # Try as a list item
                    a = row.find("a")
                    if not a:
                        continue
                    title = a.get_text(strip=True)
                    href = a["href"]
                    # Alert number from title or URL
                    m = re.search(r"(\d{2}-\d{3})", title + href)
                    alert_num = m.group(1) if m else title[:20]
                    detail_url = href if href.startswith("http") else urljoin(IA_BASE, href)
                    results.append((alert_num, title[:300], detail_url))
                    continue

                alert_num_text = cols[0].get_text(strip=True)
                title_col = cols[1] if len(cols) > 1 else cols[0]
                title = title_col.get_text(strip=True)
                a = title_col.find("a") or row.find("a")
                if not a:
                    continue
                href = a["href"]
                detail_url = href if href.startswith("http") else urljoin(IA_BASE, href)
                m = re.search(r"(\d{2}-\d{3})", alert_num_text)
                alert_num = m.group(1) if m else alert_num_text[:20]
                results.append((alert_num, title[:300], detail_url))
            except Exception:
                continue

        # Follow pagination
        next_link = soup.find("a", rel="next") or soup.find(
            "a", string=re.compile(r"next|>", re.I)
        )
        page_url = None
        if next_link and next_link.get("href"):
            href = next_link["href"]
            page_url = href if href.startswith("http") else urljoin(IA_LIST_URL, href)

        await asyncio.sleep(0.35)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed FDA import alert records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info(f"Import alerts seeder — dry_run={args.dry_run}")

    existing_ids: set[str] = set()
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            for line in f:
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
    log.info(f"  {len(existing_ids)} existing records to skip")

    all_records: list[dict] = []
    seen_ids = set(existing_ids)

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:

        log.info("Scraping FDA import alert list…")
        alerts = await scrape_alert_list(client)
        log.info(f"  Found {len(alerts)} import alerts")

        for alert_num, title, detail_url in alerts:
            rec_id = f"ia-{re.sub(r'[^a-z0-9]+', '-', alert_num.lower())}"
            if rec_id in seen_ids:
                continue

            try:
                detail = await fetch_alert_detail(client, detail_url)
                await asyncio.sleep(0.35)

                seen_ids.add(rec_id)
                all_records.append({
                    "id": rec_id,
                    "alert_number": alert_num,
                    "title": title[:300],
                    "alert_type": detail.get("alert_type", "DWPE"),
                    "country": detail.get("country", "")[:200],
                    "product": detail.get("product", title)[:500],
                    "charges": detail.get("charges", "")[:1000],
                    "cfr_citations": detail.get("cfr_citations", []),
                    "firms_on_list": detail.get("firms_on_list", []),
                    "source_url": detail_url,
                    "source_type": "import_alert",
                    "agency": "FDA",
                })
            except Exception as e:
                log.debug(f"Alert {alert_num} error: {e}")
                continue

    log.info(f"Total new import alert records: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['alert_number']}] {r['title'][:80]} — {r['country']}")
        log.info("Dry run — no file written")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if existing_ids else "w"
    with open(OUTPUT_PATH, mode, encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"{'Appended' if existing_ids else 'Written'} {len(all_records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
