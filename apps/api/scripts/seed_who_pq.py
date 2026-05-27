"""
WHO Prequalification Seeder
============================
Scrapes the WHO Prequalification website (extranet.who.int/prequal/) for
inspection outcomes, notices of concern, suspensions, and delistings, and
writes rag_index/who_pq.jsonl.

Usage:
    cd apps/api
    python scripts/seed_who_pq.py
    python scripts/seed_who_pq.py --dry-run
"""
import asyncio
import argparse
import json
import logging
import re
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_who_pq")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "who_pq.jsonl"

WHO_PQ_BASE = "https://extranet.who.int/prequal"

# WHO PQ data endpoints — try multiple paths as the site reorganizes
WHO_PQ_ENDPOINTS = [
    ("inspection_reports",    "/content/inspection-reports"),
    ("notice_of_concern",     "/content/notices-concern"),
    ("suspension",            "/content/suspensions"),
    ("delisting",             "/content/delistings"),
    ("inspection_outcomes",   "/norms-and-standards/inspection-outcomes"),
    ("medicines_reports",     "/medicines/inspection-reports"),
]

# WHO PQ also exposes some data via their API
WHO_PQ_API_ENDPOINTS = [
    ("inspection_reports",   "https://extranet.who.int/prequal/api/inspection-reports?_format=json"),
    ("notices",              "https://extranet.who.int/prequal/api/notices-concern?_format=json"),
]


def _parse_date(text: str) -> str:
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text.strip()[:20]


def _record_id(company: str, date: str, notice_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{company[:20]}-{date[:10]}".lower()).strip("-")
    return f"who-pq-{notice_type[:6]}-{slug}"


async def scrape_who_pq_page(
    client: httpx.AsyncClient,
    notice_type: str,
    base_url: str,
) -> list[dict]:
    """Scrape a WHO PQ listing page and all pagination."""
    records: list[dict] = []
    page_url: Optional[str] = base_url

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            # Some WHO PQ paths require authentication — skip gracefully
            if resp.status_code in (401, 403):
                log.info(f"  {notice_type}: access restricted at {page_url}")
                break
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.debug(f"WHO PQ page fetch failed ({page_url}): {e}")
            break

        # Parse table rows
        rows = soup.select("table tbody tr, .views-row, article, .node")
        for row in rows:
            try:
                text = row.get_text(" ", strip=True)
                text = re.sub(r"\s+", " ", text)
                if len(text) < 20:
                    continue

                cols = row.find_all("td")
                if cols:
                    company = cols[0].get_text(strip=True) if cols else ""
                    product = cols[1].get_text(strip=True) if len(cols) > 1 else ""
                    date_raw = cols[2].get_text(strip=True) if len(cols) > 2 else ""
                    outcome = cols[3].get_text(strip=True) if len(cols) > 3 else notice_type
                else:
                    # Try to parse unstructured list items
                    company_tag = row.find(["h2", "h3", "h4", "strong"])
                    company = company_tag.get_text(strip=True) if company_tag else text[:50]
                    product = ""
                    date_raw = ""
                    outcome = notice_type

                    date_match = re.search(
                        r'\b(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b',
                        text
                    )
                    if date_match:
                        date_raw = date_match.group(1)

                date = _parse_date(date_raw) if date_raw else ""
                if not company:
                    continue

                # Get detail URL
                a_tag = row.find("a")
                detail_url = ""
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    detail_url = href if href.startswith("http") else urljoin(WHO_PQ_BASE, href)

                rec_id = _record_id(company, date or str(datetime.now().year), notice_type)
                records.append({
                    "id": rec_id,
                    "company": company[:255],
                    "product": product[:500],
                    "inspection_date": date,
                    "outcome": outcome[:200],
                    "notice_type": notice_type,
                    "source_url": detail_url or page_url,
                    "source_text": text[:500],
                    "agency": "WHO",
                    "source_type": "who_pq",
                })
            except Exception:
                continue

        # Pagination
        next_link = (
            soup.find("a", rel="next")
            or soup.find("li", class_=re.compile(r"pager.*next|next.*pager"))
            or soup.find("a", string=re.compile(r"next|›|»", re.I))
        )
        page_url = None
        if next_link:
            a = next_link if next_link.name == "a" else next_link.find("a")
            if a and a.get("href"):
                href = a["href"]
                page_url = href if href.startswith("http") else urljoin(base_url, href)

        await asyncio.sleep(0.35)

    return records


async def fetch_who_pq_api(
    client: httpx.AsyncClient,
    notice_type: str,
    api_url: str,
) -> list[dict]:
    """Try the WHO PQ JSON API endpoints."""
    records = []
    page_url: Optional[str] = api_url

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            if resp.status_code in (401, 403, 404):
                break
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.debug(f"WHO PQ API failed ({page_url}): {e}")
            break

        items = data if isinstance(data, list) else data.get("results", data.get("data", []))
        if not items:
            break

        for item in items:
            try:
                company = (
                    item.get("manufacturer", item.get("company", item.get("title", "")))
                )
                product = item.get("product", item.get("medicine", ""))
                date_raw = item.get("date", item.get("inspection_date", ""))
                outcome = item.get("outcome", item.get("status", notice_type))
                source_url = item.get("url", item.get("link", api_url))
                if isinstance(source_url, dict):
                    source_url = source_url.get("uri", api_url)

                date = _parse_date(str(date_raw)) if date_raw else ""
                rec_id = _record_id(str(company), date, notice_type)
                records.append({
                    "id": rec_id,
                    "company": str(company)[:255],
                    "product": str(product)[:500],
                    "inspection_date": date,
                    "outcome": str(outcome)[:200],
                    "notice_type": notice_type,
                    "source_url": str(source_url)[:500],
                    "agency": "WHO",
                    "source_type": "who_pq",
                })
            except Exception:
                continue

        # Check for next page URL
        next_url = data.get("next", data.get("links", {}).get("next", ""))
        if isinstance(next_url, dict):
            next_url = next_url.get("href", "")
        page_url = str(next_url) if next_url else None
        await asyncio.sleep(0.35)

    return records


async def main():
    parser = argparse.ArgumentParser(description="Seed WHO Prequalification records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info(f"WHO PQ seeder — dry_run={args.dry_run}")

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

        # Try JSON API endpoints first
        for notice_type, api_url in WHO_PQ_API_ENDPOINTS:
            log.info(f"Trying WHO PQ API: {notice_type}…")
            records = await fetch_who_pq_api(client, notice_type, api_url)
            if records:
                log.info(f"  API returned {len(records)} {notice_type} records")
                new = [r for r in records if r["id"] not in seen_ids]
                for r in new:
                    seen_ids.add(r["id"])
                all_records.extend(new)

        # HTML scrape of public pages
        for notice_type, path in WHO_PQ_ENDPOINTS:
            url = WHO_PQ_BASE + path
            log.info(f"Scraping WHO PQ {notice_type} ({url})…")
            records = await scrape_who_pq_page(client, notice_type, url)
            new = [r for r in records if r["id"] not in seen_ids]
            for r in new:
                seen_ids.add(r["id"])
            all_records.extend(new)
            log.info(f"  {notice_type}: {len(new)} new records")

    log.info(f"Total new WHO PQ records: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['notice_type']}] {r['company']} — {r['inspection_date']}")
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
