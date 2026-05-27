"""
eCFR Live Seeder
================
Pulls live Title 21 CFR text from the eCFR versioner API (ecfr.gov) and
writes rag_index/regulatory_corpus.jsonl, replacing the static file built
by ingest_cfr.py.

Target parts: 11, 58, 110, 111, 117, 210, 211, 212, 600-range, 820

Usage:
    cd apps/api
    python scripts/seed_ecfr.py
    python scripts/seed_ecfr.py --dry-run
    python scripts/seed_ecfr.py --parts 211,820
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

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_ecfr")

SCRIPT_DIR = Path(__file__).parent
OUTPUT_PATH = SCRIPT_DIR.parent / "rag_index" / "regulatory_corpus.jsonl"

ECFR_API = "https://www.ecfr.gov/api/versioner/v1"
ECFR_READER = "https://www.ecfr.gov/current/title-21"

# Parts the user explicitly requested, plus known 600-range biologics parts
DEFAULT_TARGET_PARTS = {
    "11", "58",                              # ER/ES, GLP
    "110", "111", "117",                     # Food safety
    "210", "211", "212",                     # cGMP pharma
    "600", "601", "606", "607", "610",       # Biologics
    "620", "630", "640", "660", "680",       # Biologics (cont'd)
    "820",                                   # QSR devices
}

PART_META = {
    "11":  {"desc": "Electronic Records and Signatures",         "sub_sectors": ["SS-D1","SS-D2","SS-D3","SS-B1","SS-B2","SS-MD1"], "doc_cats": ["SOP","ATM","Validation","CAPA","Deviation","LIR"]},
    "58":  {"desc": "Good Laboratory Practice",                  "sub_sectors": ["SS-D1","SS-D2","SS-B1"],          "doc_cats": ["SOP","ATM","Validation"]},
    "110": {"desc": "cGMP — Human Food",                         "sub_sectors": ["SS-D4"],                          "doc_cats": ["SOP","Deviation"]},
    "111": {"desc": "cGMP — Dietary Supplements",                "sub_sectors": ["SS-D4"],                          "doc_cats": ["SOP","CAPA","Deviation"]},
    "117": {"desc": "FSMA Preventive Controls — Human Food",     "sub_sectors": ["SS-D4"],                          "doc_cats": ["SOP","CAPA","Deviation"]},
    "210": {"desc": "cGMP — General",                            "sub_sectors": ["SS-D1","SS-D2","SS-D3","SS-D4"],  "doc_cats": ["SOP","CAPA","Deviation","LIR","ATM","Validation"]},
    "211": {"desc": "cGMP — Finished Pharmaceuticals",           "sub_sectors": ["SS-D1","SS-D2","SS-D3","SS-D4"],  "doc_cats": ["SOP","CAPA","Deviation","LIR","ATM","Validation"]},
    "212": {"desc": "cGMP — PET Drugs",                          "sub_sectors": ["SS-D3"],                          "doc_cats": ["SOP","Validation"]},
    "600": {"desc": "Biological Products — General",             "sub_sectors": ["SS-B1","SS-B2","SS-VAC"],         "doc_cats": ["SOP","CAPA","Validation"]},
    "601": {"desc": "Biological Products — Licensing",           "sub_sectors": ["SS-B1","SS-B2","SS-VAC"],         "doc_cats": ["SOP"]},
    "606": {"desc": "cGMP — Blood and Blood Components",         "sub_sectors": ["SS-B1","SS-VAC"],                 "doc_cats": ["SOP","ATM","Validation"]},
    "607": {"desc": "Establishment Registration — Biologics",    "sub_sectors": ["SS-B1","SS-VAC"],                 "doc_cats": ["SOP"]},
    "610": {"desc": "Biological Products — General Standards",   "sub_sectors": ["SS-B1","SS-B2","SS-VAC"],         "doc_cats": ["SOP","ATM","Validation"]},
    "620": {"desc": "Bacterial Vaccines and Toxoids",            "sub_sectors": ["SS-VAC"],                         "doc_cats": ["SOP","Validation"]},
    "630": {"desc": "General Requirements for Blood",            "sub_sectors": ["SS-B1"],                          "doc_cats": ["SOP","Validation"]},
    "640": {"desc": "Blood and Blood Products",                  "sub_sectors": ["SS-B1"],                          "doc_cats": ["SOP","ATM","Validation"]},
    "660": {"desc": "Diagnostic Devices — Biologics",            "sub_sectors": ["SS-DX1"],                         "doc_cats": ["SOP","ATM","Validation"]},
    "680": {"desc": "Biologics Miscellaneous",                   "sub_sectors": ["SS-B1","SS-B2","SS-VAC"],         "doc_cats": ["SOP","Validation"]},
    "820": {"desc": "Quality System Regulation — Medical Devices","sub_sectors": ["SS-MD1","SS-DX1"],               "doc_cats": ["SOP","CAPA","Deviation","Validation"]},
}

SECTION_KW_TO_DOC_CATS: list[tuple[list[str], list[str]]] = [
    (["complaint","investigation","corrective","capa","deviation","recall"],  ["CAPA","Deviation"]),
    (["out-of-specification","oos","laboratory","test","analytical","method"],["ATM","LIR"]),
    (["validation","qualify","calibration","process"],                        ["Validation"]),
    (["procedure","sop","written","record","documentation"],                  ["SOP"]),
    (["stability","shelf life"],                                              ["ATM","Validation"]),
    (["electronic","computer","software","audit trail"],                      ["SOP","Validation"]),
]


def _enrich_doc_cats(text: str, defaults: list[str]) -> list[str]:
    tl = text.lower()
    cats = set(defaults)
    for kws, extra in SECTION_KW_TO_DOC_CATS:
        if any(kw in tl for kw in kws):
            cats.update(extra)
    return sorted(cats)


def _section_id(section: str) -> str:
    return f"cfr-21-{section.replace('.', '-')}"


def _parse_sections_from_html(html: str, part: str) -> list[dict]:
    """Extract individual CFR sections from eCFR HTML reader page."""
    soup = BeautifulSoup(html, "lxml")
    meta = PART_META.get(part, {"desc": f"21 CFR Part {part}", "sub_sectors": [], "doc_cats": []})
    records = []

    # Try multiple eCFR HTML structure patterns
    # Pattern 1: <div class="section" id="p-N.N"> with <h4 class="section-head">
    section_divs = soup.find_all("div", class_=lambda c: c and "section" in c.split())
    if not section_divs:
        # Pattern 2: <section> elements
        section_divs = soup.find_all("section")

    for div in section_divs:
        try:
            # Extract section number from id attribute or heading text
            sec_id = div.get("id", "")
            sect_num = ""
            subject = ""

            # Heading contains "§ N.N Title"
            heading = div.find(["h4", "h3", "h5"], class_=lambda c: c and ("section-head" in c or "heading" in c))
            if not heading:
                heading = div.find(["h4", "h3", "h5"])

            if heading:
                heading_text = heading.get_text(" ", strip=True)
                m = re.match(r"§\s*([\d.]+[a-z]?)\s*(.*)", heading_text)
                if m:
                    sect_num = m.group(1).strip()
                    subject = m.group(2).strip().rstrip(".")

            if not sect_num:
                # Try id like "p-211.22" or "section-211.22"
                m = re.search(r"(\d+\.\d+[a-z]?)", sec_id)
                if m:
                    sect_num = m.group(1)

            if not sect_num or not sect_num.startswith(part + "."):
                continue

            # Extract body text (skip the heading itself)
            if heading:
                heading.decompose()
            content = div.get_text(" ", strip=True)
            content = re.sub(r"\s+", " ", content).strip()

            if len(content) < 20:
                continue

            records.append({
                "id": _section_id(sect_num),
                "cfr_citation": f"21 CFR {sect_num}",
                "citation_reference": f"21 CFR {sect_num}",
                "section": sect_num,
                "part": part,
                "title": subject,
                "text": content,
                "content": content,
                "agency": "FDA",
                "document_type": "regulation",
                "hierarchy_level": 2,
                "sub_sectors": meta["sub_sectors"],
                "document_categories": _enrich_doc_cats(content, meta["doc_cats"]),
                "effective_date": datetime.now().strftime("%Y-%m-%d"),
                "is_current": True,
                "source": "ecfr-live",
                "part_description": meta["desc"],
            })
        except Exception as e:
            log.debug(f"Section parse error in part {part}: {e}")
            continue

    return records


async def fetch_ecfr_version(client: httpx.AsyncClient) -> str:
    """Return the latest eCFR version date string."""
    try:
        resp = await client.get(f"{ECFR_API}/versions/title-21.json", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # Response has a list of version objects; pick the most recent
        versions = data.get("content_versions", data.get("versions", []))
        if versions:
            return sorted(versions, key=lambda v: v.get("date", ""))[-1].get("date", "current")
    except Exception as e:
        log.debug(f"Version fetch failed: {e}")
    return "current"


async def find_part_paths(client: httpx.AsyncClient, date: str, target_parts: set[str]) -> dict[str, str]:
    """
    Walk the eCFR structure tree and return {part_num: full_url_path} for each
    target part found under title 21, chapter I.
    """
    paths: dict[str, str] = {}
    try:
        resp = await client.get(f"{ECFR_API}/structure/{date}/title-21.json", timeout=30)
        resp.raise_for_status()
        tree = resp.json()
    except Exception as e:
        log.warning(f"Structure fetch failed: {e}; will use direct reader URLs")
        return paths

    def walk(node: dict, ancestors: list[tuple[str, str]]):
        ntype = node.get("type", "")
        ident = str(node.get("identifier", node.get("label", "")))

        segment: Optional[str] = None
        if ntype == "title":
            segment = f"title-{ident}"
        elif ntype == "chapter":
            segment = f"chapter-{ident}"
        elif ntype == "subchapter":
            segment = f"subchapter-{ident}"
        elif ntype == "part":
            segment = f"part-{ident}"
            if ident in target_parts:
                full = "/".join(s for _, s in ancestors) + "/" + segment
                paths[ident] = full.lstrip("/")
            return  # don't recurse into sections

        if segment is not None:
            new_ancestors = ancestors + [(ident, segment)]
        else:
            new_ancestors = ancestors

        for child in node.get("children", []):
            walk(child, new_ancestors)

    walk(tree, [])
    return paths


async def fetch_part_sections(
    client: httpx.AsyncClient,
    part: str,
    part_path: Optional[str],
    date: str,
) -> list[dict]:
    """Fetch all sections for a CFR part, using API path if known, else reader URL."""
    if part_path:
        # Try XML via versioner API
        xml_url = f"{ECFR_API}/full/{date}/{part_path}.xml"
        try:
            resp = await client.get(xml_url, timeout=60, follow_redirects=True)
            if resp.status_code == 200:
                records = _parse_sections_from_html(resp.text, part)
                if records:
                    return records
        except Exception as e:
            log.debug(f"API XML fetch failed for part {part}: {e}")

    # Fallback: HTML reader
    reader_url = f"{ECFR_READER}/part-{part}"
    try:
        resp = await client.get(reader_url, timeout=60, follow_redirects=True)
        if resp.status_code == 200:
            return _parse_sections_from_html(resp.text, part)
    except Exception as e:
        log.warning(f"Reader HTML fetch failed for part {part}: {e}")

    return []


async def main():
    parser = argparse.ArgumentParser(description="Seed eCFR live regulatory corpus")
    parser.add_argument("--parts", default="", help="Comma-separated part numbers (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Count records without writing")
    args = parser.parse_args()

    target = set(p.strip() for p in args.parts.split(",") if p.strip()) or DEFAULT_TARGET_PARTS

    log.info(f"eCFR seeder — parts={sorted(target)} dry_run={args.dry_run}")

    async with httpx.AsyncClient(
        headers={"User-Agent": "Clyira/1.0 (regulatory corpus builder; contact: admin@clyira.ai)"},
        follow_redirects=True,
    ) as client:
        date = await fetch_ecfr_version(client)
        log.info(f"eCFR version date: {date}")
        await asyncio.sleep(0.3)

        part_paths = await find_part_paths(client, date, target)
        log.info(f"Located {len(part_paths)}/{len(target)} parts via structure API")
        await asyncio.sleep(0.3)

        all_records: list[dict] = []
        seen_ids: set[str] = set()

        for part in sorted(target, key=lambda p: int(p)):
            path = part_paths.get(part)
            log.info(f"  Fetching Part {part}…")
            records = await fetch_part_sections(client, part, path, date)
            new = [r for r in records if r["id"] not in seen_ids]
            for r in new:
                seen_ids.add(r["id"])
            all_records.extend(new)
            log.info(f"    Part {part}: {len(new)} sections")
            await asyncio.sleep(0.4)

    log.info(f"Total sections fetched: {len(all_records)}")

    if args.dry_run:
        for r in all_records[:5]:
            print(f"  [{r['citation_reference']}] {r['title'][:80]}")
        log.info("Dry run — no file written")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"Written {len(all_records)} sections to {OUTPUT_PATH}")

    from collections import Counter
    by_part = Counter(r["part"] for r in all_records)
    for p, cnt in sorted(by_part.items(), key=lambda x: int(x[0])):
        desc = PART_META.get(p, {}).get("desc", "")
        log.info(f"  Part {p:>4} ({desc[:40]}): {cnt} sections")


if __name__ == "__main__":
    asyncio.run(main())
