"""
EU GMP Seeder
=============
Downloads EudraLex Volume 4 PDFs (main chapters + Annexes 1–19) from
health.ec.europa.eu, extracts text, and writes rag_index/eu_gmp.jsonl.

Usage:
    cd apps/api
    python scripts/seed_eu_gmp.py
    python scripts/seed_eu_gmp.py --dry-run
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
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_eu_gmp")

OUTPUT_PATH = Path(__file__).parent.parent / "rag_index" / "eu_gmp.jsonl"

EUDRALEX_URL = "https://health.ec.europa.eu/medicinal-products/eudralex/eudralex-volume-4_en"
EC_BASE = "https://health.ec.europa.eu"

# Fallback known document list if scraping yields fewer results than expected
KNOWN_DOCUMENTS = [
    ("Chapter 1",  "Quality Management",              "main"),
    ("Chapter 2",  "Personnel",                       "main"),
    ("Chapter 3",  "Premises and Equipment",          "main"),
    ("Chapter 4",  "Documentation",                   "main"),
    ("Chapter 5",  "Production",                      "main"),
    ("Chapter 6",  "Quality Control",                 "main"),
    ("Chapter 7",  "Outsourced Activities",           "main"),
    ("Chapter 8",  "Complaints and Recalls",          "main"),
    ("Chapter 9",  "Self Inspection",                 "main"),
    ("Annex 1",    "Manufacture of Sterile Medicinal Products",   "annex"),
    ("Annex 2",    "Biological Active Substances and Medicinal Products", "annex"),
    ("Annex 3",    "Radiopharmaceuticals",            "annex"),
    ("Annex 4",    "Veterinary Medicinal Products",   "annex"),
    ("Annex 5",    "Immunological Veterinary Medicinal Products", "annex"),
    ("Annex 6",    "Medicinal Gases",                 "annex"),
    ("Annex 7",    "Herbal Medicinal Products",       "annex"),
    ("Annex 8",    "Sampling of Starting and Packaging Materials", "annex"),
    ("Annex 9",    "Liquids, Creams and Ointments",   "annex"),
    ("Annex 10",   "Manufacture of Pressurised Metered Dose Aerosol", "annex"),
    ("Annex 11",   "Computerised Systems",            "annex"),
    ("Annex 12",   "Use of Ionising Radiation",       "annex"),
    ("Annex 13",   "Investigational Medicinal Products", "annex"),
    ("Annex 14",   "Manufacture of ATMPs",            "annex"),
    ("Annex 15",   "Qualification and Validation",    "annex"),
    ("Annex 16",   "Certification by a QP and Batch Release", "annex"),
    ("Annex 17",   "Parametric Release",              "annex"),
    ("Annex 18",   "GMP Guide for Active Substances", "annex"),
    ("Annex 19",   "Reference and Retention Samples", "annex"),
    ("Part II",    "Basic Requirements for Active Substances", "part"),
]


def _doc_key(doc_label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", doc_label.lower()).strip("-")


def _chunk_text(text: str, doc_label: str, doc_title: str, doc_type: str, source_url: str) -> list[dict]:
    """Split PDF text into sections at numbered headings."""
    heading_re = re.compile(
        r'^(?:\d+(?:\.\d+)*\.?\s+[A-Z]|PRINCIPLE|SCOPE|INTRODUCTION|GENERAL|'
        r'REQUIREMENTS?|REFERENCES?|GLOSSARY|APPENDIX|ANNEX\s+\d)',
        re.MULTILINE,
    )
    lines = text.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_head = "Introduction"
    current_body: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if heading_re.match(stripped) and len(stripped) < 120:
            if current_body:
                sections.append((current_head, current_body))
            current_head = stripped
            current_body = []
        else:
            current_body.append(stripped)

    if current_body:
        sections.append((current_head, current_body))

    key = _doc_key(doc_label)
    records = []
    for i, (heading, body_lines) in enumerate(sections):
        body = " ".join(body_lines).strip()
        if len(body) < 50:
            continue
        records.append({
            "id": f"eu-gmp-{key}-{i}",
            "document": doc_label,
            "title": doc_title,
            "document_type": doc_type,
            "section": heading[:200],
            "text": body[:4000],
            "source_url": source_url,
            "agency": "EMA",
            "source_type": "eu_gmp",
        })
    return records


async def extract_pdf_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as e:
        log.warning(f"PDF download failed ({url}): {e}")
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
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        pass

    log.warning(f"PDF text extraction failed for {url}")
    return ""


async def scrape_eudralex_index(client: httpx.AsyncClient) -> list[tuple[str, str, str, str]]:
    """
    Scrape EudraLex Volume 4 index and return
    list of (label, title, doc_type, pdf_url).
    Follows pagination until exhausted.
    """
    results: list[tuple[str, str, str, str]] = []
    page_url: Optional[str] = EUDRALEX_URL

    while page_url:
        try:
            resp = await client.get(page_url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            log.warning(f"EudraLex index fetch failed ({page_url}): {e}")
            break

        # Find PDF links with annex/chapter patterns in anchor text or href
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            href = a["href"]
            link_text = a.get_text(" ", strip=True)
            pdf_url = href if href.startswith("http") else urljoin(EC_BASE, href)

            # Determine document label from link text or URL
            label = ""
            doc_type = "annex"

            m = re.search(r"(Annex\s+\d+|Chapter\s+\d+|Part\s+II)", link_text, re.I)
            if m:
                label = m.group(1).title()
            else:
                m = re.search(r"annex[_-]?(\d+)|chapter[_-]?(\d+)|part[_-]?(ii)", href, re.I)
                if m:
                    if m.group(1):
                        label = f"Annex {m.group(1)}"
                    elif m.group(2):
                        label = f"Chapter {m.group(2)}"
                        doc_type = "main"
                    else:
                        label = "Part II"
                        doc_type = "part"

            if not label:
                continue
            if "chapter" in label.lower():
                doc_type = "main"

            title = link_text[:200] if link_text else label
            if not any(r[0] == label for r in results):
                results.append((label, title, doc_type, pdf_url))

        # Follow pagination
        next_link = soup.find("a", rel="next") or soup.find(
            "a", string=re.compile(r"next|>", re.I)
        )
        page_url = None
        if next_link and next_link.get("href"):
            href = next_link["href"]
            page_url = href if href.startswith("http") else urljoin(EUDRALEX_URL, href)

        await asyncio.sleep(0.35)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Seed EU GMP corpus")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log.info(f"EU GMP seeder — dry_run={args.dry_run}")

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:
        log.info("Scraping EudraLex Volume 4 index…")
        documents = await scrape_eudralex_index(client)
        log.info(f"  Found {len(documents)} documents on index page")

        # Supplement with known list for any gaps
        found_labels = {d[0] for d in documents}
        for label, title, doc_type in KNOWN_DOCUMENTS:
            if label not in found_labels:
                documents.append((label, title, doc_type, ""))

        all_records: list[dict] = []
        seen_ids: set[str] = set()

        for label, title, doc_type, pdf_url in sorted(documents, key=lambda x: x[0]):
            if not pdf_url:
                log.debug(f"  Skipping {label} — no PDF URL discovered")
                continue
            log.info(f"  Processing {label}: {title[:60]}")
            text = await extract_pdf_text(client, pdf_url)
            if not text.strip():
                log.warning(f"  No text for {label}")
                await asyncio.sleep(0.3)
                continue
            chunks = _chunk_text(text, label, title, doc_type, pdf_url)
            new = [c for c in chunks if c["id"] not in seen_ids]
            for c in new:
                seen_ids.add(c["id"])
            all_records.extend(new)
            log.info(f"    {label}: {len(new)} sections")
            await asyncio.sleep(0.4)

    log.info(f"Total EU GMP sections: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['document']}] {r['section'][:80]}")
        log.info("Dry run — no file written")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"Written {len(all_records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
