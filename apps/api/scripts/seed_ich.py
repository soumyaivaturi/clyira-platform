"""
ICH Guidelines Seeder
=====================
Scrapes ich.org for Q1–Q14, E6(R3), and S-series PDFs, extracts text,
and writes rag_index/ich_guidelines.jsonl.

Usage:
    cd apps/api
    python scripts/seed_ich.py
    python scripts/seed_ich.py --dry-run
    python scripts/seed_ich.py --series Q   # only Quality series
"""
import asyncio
import argparse
import hashlib
import io
import json
import logging
import re
import sys
import os
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_ich")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "ich_guidelines.jsonl"

ICH_BASE = "https://www.ich.org"
ICH_GUIDELINES_ROOT = "https://www.ich.org/page/ich-guidelines"

# Guideline series pages on ich.org
SERIES_PAGES = {
    "Q": "https://www.ich.org/page/quality-guidelines",
    "E": "https://www.ich.org/page/efficacy-guidelines",
    "S": "https://www.ich.org/page/safety-guidelines",
    "M": "https://www.ich.org/page/multidisciplinary-guidelines",
}

# Priority guidelines — also used as fallback scrape targets
PRIORITY_GUIDELINES = [
    # Quality
    "Q1A", "Q1B", "Q1C", "Q1D", "Q1E", "Q1F",
    "Q2(R1)", "Q2(R2)",
    "Q3A", "Q3B", "Q3C", "Q3D",
    "Q4B",
    "Q5A", "Q5B", "Q5C", "Q5D", "Q5E",
    "Q6A", "Q6B",
    "Q7",
    "Q8(R2)",
    "Q9(R1)",
    "Q10",
    "Q11",
    "Q12",
    "Q13",
    "Q14",
    # Efficacy
    "E6(R3)",
    # Safety
    "S1A", "S1B", "S1C",
    "S2(R1)",
    "S3A", "S3B",
    "S4",
    "S5(R3)",
    "S6(R1)",
    "S7A", "S7B",
    "S8",
    "S9",
    "S10",
    "S11",
    "S12",
]


def _guideline_id_from_text(text: str) -> Optional[str]:
    """Extract a normalized guideline ID like 'Q7' from heading text."""
    m = re.search(
        r'\b(Q\d+[A-Z]?(?:\(R\d+\))?|E\d+[A-Z]?(?:\(R\d+\))?|S\d+[A-Z]?(?:\(R\d+\))?|M\d+[A-Z]?(?:\(R\d+\))?)',
        text, re.IGNORECASE
    )
    return m.group(1).upper() if m else None


def _chunk_text_by_headings(text: str, guideline_id: str, title: str) -> list[dict]:
    """Split PDF text into sections using numbered-heading heuristics."""
    # Detect lines that look like section headings: "1.", "2.1", "3.2.1", "APPENDIX"
    heading_re = re.compile(
        r'^(?:\d+(?:\.\d+)*\.?\s+[A-Z]|[A-Z]{3,}(?:\s+[A-Z]+)*\s*$)',
        re.MULTILINE,
    )
    lines = text.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Introduction"
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if heading_re.match(stripped) and len(stripped) < 120:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = stripped
            current_lines = []
        else:
            current_lines.append(stripped)

    if current_lines:
        sections.append((current_heading, current_lines))

    records = []
    for i, (heading, body_lines) in enumerate(sections):
        body = " ".join(body_lines).strip()
        if len(body) < 50:
            continue
        rec_id = hashlib.md5(f"{guideline_id}-{i}-{heading[:40]}".encode()).hexdigest()[:16]
        records.append({
            "id": f"ich-{guideline_id.lower().replace('(','').replace(')','').replace('/','')}-{i}",
            "guideline_id": guideline_id,
            "title": title,
            "section": heading[:200],
            "text": body[:4000],
            "source_type": "ich_guideline",
        })
    return records


async def extract_pdf_text(client: httpx.AsyncClient, pdf_url: str) -> str:
    """Download a PDF and extract its full text."""
    try:
        resp = await client.get(pdf_url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        log.warning(f"PDF download failed ({pdf_url}): {e}")
        return ""

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception:
        pass

    log.warning(f"PDF text extraction failed for {pdf_url} — pdfplumber/PyPDF2 not available")
    return ""


async def scrape_series_page(
    client: httpx.AsyncClient, series_url: str
) -> list[tuple[str, str, str]]:
    """
    Scrape an ICH series page and return list of (guideline_id, title, pdf_url).
    Paginate if needed (ICH pages are single-page, but we follow any "next" links).
    """
    results: list[tuple[str, str, str]] = []
    page_url: Optional[str] = series_url

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.warning(f"Series page fetch failed ({page_url}): {e}")
            break

        # ICH guideline entries: look for heading + PDF links in structured lists
        for item in soup.find_all(["article", "div", "li"], class_=lambda c: c and any(
            k in c for k in ["guideline", "document", "document-item", "card"]
        )):
            title_tag = item.find(["h2", "h3", "h4", "h5", "a"])
            if not title_tag:
                continue
            heading_text = title_tag.get_text(" ", strip=True)
            gid = _guideline_id_from_text(heading_text)
            if not gid:
                continue
            # Find a PDF link within this item
            pdf_link = item.find("a", href=re.compile(r"\.pdf", re.I))
            if pdf_link:
                href = pdf_link["href"]
                pdf_url = href if href.startswith("http") else urljoin(ICH_BASE, href)
                results.append((gid, heading_text[:300], pdf_url))

        # Also scan for any PDF links with guideline IDs in href
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a["href"]
            link_text = a.get_text(" ", strip=True)
            gid = _guideline_id_from_text(href) or _guideline_id_from_text(link_text)
            if gid and not any(r[0] == gid for r in results):
                pdf_url = href if href.startswith("http") else urljoin(ICH_BASE, href)
                results.append((gid, link_text[:300] or gid, pdf_url))

        # Follow pagination if present
        next_link = soup.find("a", string=re.compile(r"next|>", re.I), rel=lambda r: r and "next" in r)
        if not next_link:
            next_link = soup.find("a", rel="next")
        page_url = None
        if next_link and next_link.get("href"):
            href = next_link["href"]
            page_url = href if href.startswith("http") else urljoin(series_url, href)

        await asyncio.sleep(0.35)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed ICH guideline corpus")
    parser.add_argument("--series", default="", help="Series letters to fetch (Q/E/S/M), default all")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    series_filter = set(args.series.upper().split(",")) if args.series else set(SERIES_PAGES.keys())
    log.info(f"ICH seeder — series={series_filter} dry_run={args.dry_run}")

    all_records: list[dict] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:

        for series, series_url in SERIES_PAGES.items():
            if series not in series_filter:
                continue
            log.info(f"Scraping ICH {series}-series page…")
            guidelines = await scrape_series_page(client, series_url)
            log.info(f"  Found {len(guidelines)} {series}-series guidelines")

            for gid, title, pdf_url in guidelines:
                log.info(f"  Processing {gid}: {title[:60]}")
                text = await extract_pdf_text(client, pdf_url)
                if not text.strip():
                    log.warning(f"  No text extracted for {gid}")
                    await asyncio.sleep(0.3)
                    continue

                chunks = _chunk_text_by_headings(text, gid, title)
                new = [c for c in chunks if c["id"] not in seen_ids]
                for c in new:
                    c["source_url"] = pdf_url
                    seen_ids.add(c["id"])
                all_records.extend(new)
                log.info(f"    {gid}: {len(new)} sections extracted")
                await asyncio.sleep(0.4)

    log.info(f"Total ICH sections: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['guideline_id']}] {r['section'][:80]}")
        log.info("Dry run — no file written")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"Written {len(all_records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
