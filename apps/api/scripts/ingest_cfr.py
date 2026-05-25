"""
CFR Title 21 Ingestion Script
==============================
Parses the 9 CFR-Title21-XML volumes from the Clyira-Corpus and writes
a regulatory_corpus.jsonl to apps/api/rag_index/ for bundling in Docker.

Run from apps/api/:
    python scripts/ingest_cfr.py

Output: apps/api/rag_index/regulatory_corpus.jsonl
"""
import json
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

# ── Paths ────────────────────────────────────────────────────────────────────

CORPUS_ROOT = Path("/Users/bharadwajchivukula/Documents/Clyira - May 2026/Clyira-Corpus")
XML_DIR = CORPUS_ROOT / "03-Regulations" / "CFR-Title21-XML"
TXT_DIR = CORPUS_ROOT / "02-Regulatory" / "21-CFR"

SCRIPT_DIR = Path(__file__).parent
OUTPUT_PATH = SCRIPT_DIR.parent / "rag_index" / "regulatory_corpus.jsonl"

# ── Parts to index ────────────────────────────────────────────────────────────
# Maps part number → (volume, description, sub_sectors, document_categories)
PARTS_CONFIG = {
    "11": {
        "vol": 1,
        "description": "Electronic Records and Signatures",
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-B1", "SS-B2", "SS-MD1"],
        "doc_categories": ["SOP", "ATM", "Validation", "CAPA", "Deviation", "LIR"],
        "hierarchy_level": 2,
    },
    "58": {
        "vol": 1,
        "description": "Good Laboratory Practice",
        "sub_sectors": ["SS-D1", "SS-D2", "SS-B1"],
        "doc_categories": ["SOP", "ATM", "Validation"],
        "hierarchy_level": 2,
    },
    "210": {
        "vol": 4,
        "description": "Current Good Manufacturing Practice — General",
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4"],
        "doc_categories": ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation"],
        "hierarchy_level": 2,
    },
    "211": {
        "vol": 4,
        "description": "Current Good Manufacturing Practice — Finished Pharmaceuticals",
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4"],
        "doc_categories": ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation"],
        "hierarchy_level": 2,
    },
    "212": {
        "vol": 4,
        "description": "Current Good Manufacturing Practice — PET Drugs",
        "sub_sectors": ["SS-D3"],
        "doc_categories": ["SOP", "Validation"],
        "hierarchy_level": 2,
    },
    "600": {
        "vol": 7,
        "description": "Biological Products — General",
        "sub_sectors": ["SS-B1", "SS-B2", "SS-VAC"],
        "doc_categories": ["SOP", "CAPA", "Validation"],
        "hierarchy_level": 2,
    },
    "606": {
        "vol": 7,
        "description": "Current Good Manufacturing Practice — Blood and Blood Components",
        "sub_sectors": ["SS-B1", "SS-VAC"],
        "doc_categories": ["SOP", "ATM", "Validation"],
        "hierarchy_level": 2,
    },
    "610": {
        "vol": 7,
        "description": "Biological Products — General Standards",
        "sub_sectors": ["SS-B1", "SS-B2", "SS-VAC"],
        "doc_categories": ["SOP", "ATM", "Validation"],
        "hierarchy_level": 2,
    },
    "820": {
        "vol": 8,
        "description": "Quality System Regulation — Medical Devices",
        "sub_sectors": ["SS-MD1", "SS-DX1"],
        "doc_categories": ["SOP", "CAPA", "Deviation", "Validation"],
        "hierarchy_level": 2,
    },
}

# ── Sub-section keyword → document category mapping ───────────────────────────
SECTION_KEYWORD_TO_DOC_CATS: list[tuple[list[str], list[str]]] = [
    (["complaint", "investigation", "corrective", "capa", "deviation", "recall"],
     ["CAPA", "Deviation"]),
    (["out-of-specification", "oos", "laboratory", "test", "analytical", "method"],
     ["ATM", "LIR"]),
    (["validation", "qualify", "calibration", "process"],
     ["Validation"]),
    (["procedure", "sop", "written", "record", "documentation"],
     ["SOP"]),
    (["stability", "shelf life"],
     ["ATM", "Validation"]),
    (["electronic", "computer", "software", "audit trail"],
     ["SOP", "Validation"]),
]


def _get_doc_categories(section_text: str, part_defaults: list[str]) -> list[str]:
    """Refine document_categories based on section content keywords."""
    text_lower = section_text.lower()
    cats = set(part_defaults)
    for keywords, extra_cats in SECTION_KEYWORD_TO_DOC_CATS:
        if any(kw in text_lower for kw in keywords):
            cats.update(extra_cats)
    return sorted(cats)


def _extract_text_from_section(section_el) -> str:
    """Recursively extract all text from a SECTION element."""
    parts = []
    for child in section_el:
        if child.tag in ("SECTNO", "SUBJECT"):
            continue  # handled separately
        text = "".join(child.itertext()).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def parse_xml_volume(vol: int, target_parts: set[str]) -> list[dict]:
    """Parse one XML volume and return sections for the target parts."""
    xml_path = XML_DIR / f"CFR-2024-title21-vol{vol}.xml"
    if not xml_path.exists():
        print(f"  WARNING: {xml_path} not found, skipping")
        return []

    tree = ET.parse(xml_path)
    root = tree.getroot()
    records = []

    for section in root.findall(".//SECTION"):
        sectno_raw = section.findtext("SECTNO", "").strip()
        # SECTNO format: "§ 211.22" — normalize to "211.22"
        sectno = sectno_raw.replace("§", "").replace(" ", "").replace("\xa0", "").strip()
        if not sectno:
            continue

        # Extract part number
        part_match = re.match(r"^(\d+)\.", sectno)
        if not part_match:
            continue
        part_num = part_match.group(1)
        if part_num not in target_parts:
            continue

        subject = section.findtext("SUBJECT", "").strip()
        content = _extract_text_from_section(section)

        if not content.strip():
            continue

        cfg = PARTS_CONFIG[part_num]
        citation = f"21 CFR {sectno}"

        records.append({
            "id": f"cfr-21-{sectno.replace('.', '-')}",
            "citation_reference": citation,
            "section": sectno,
            "part": part_num,
            "title": subject,
            "content": content,
            "agency": "FDA",
            "document_type": "regulation",
            "hierarchy_level": cfg["hierarchy_level"],
            "sub_sectors": cfg["sub_sectors"],
            "document_categories": _get_doc_categories(content, cfg["doc_categories"]),
            "effective_date": "2024-04-01",
            "is_current": True,
            "source": f"CFR-2024-title21-vol{vol}.xml",
            "part_description": cfg["description"],
        })

    return records


def parse_txt_fallback(part: str, cfg: dict) -> list[dict]:
    """Parse the .txt file for a part when XML has no sections (shouldn't happen)."""
    txt_path = TXT_DIR / f"21CFR_Part_{part}.txt"
    if not txt_path.exists():
        return []

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    records = []

    # Match "§ NNN.NNN Title.\n---"
    section_pattern = re.compile(
        r"§\s*(\d+\.\d+[a-z]?)\s+([^\n]+)\.\n[-─]+\n(.*?)(?=§\s*\d+\.\d+|\Z)",
        re.DOTALL,
    )

    for m in section_pattern.finditer(text):
        sectno = m.group(1).strip()
        subject = m.group(2).strip()
        content = m.group(3).strip()

        # Remove legal history lines like [43 FR 45077, ...]
        content = re.sub(r"\[\s*\d+ FR.*?\]", "", content, flags=re.DOTALL).strip()

        if not content or len(content) < 30:
            continue

        records.append({
            "id": f"cfr-21-{sectno.replace('.', '-')}",
            "citation_reference": f"21 CFR {sectno}",
            "section": sectno,
            "part": part,
            "title": subject,
            "content": content,
            "agency": "FDA",
            "document_type": "regulation",
            "hierarchy_level": cfg["hierarchy_level"],
            "sub_sectors": cfg["sub_sectors"],
            "document_categories": _get_doc_categories(content, cfg["doc_categories"]),
            "effective_date": "2024-04-01",
            "is_current": True,
            "source": f"21CFR_Part_{part}.txt",
            "part_description": cfg["description"],
        })

    return records


def main():
    print(f"CFR Title 21 Ingestion — output: {OUTPUT_PATH}")

    # Group parts by volume
    vol_to_parts: dict[int, set[str]] = {}
    for part, cfg in PARTS_CONFIG.items():
        vol = cfg["vol"]
        vol_to_parts.setdefault(vol, set()).add(part)

    all_records: list[dict] = []
    seen_ids: set[str] = set()

    for vol, parts in sorted(vol_to_parts.items()):
        print(f"\nParsing vol {vol} for parts: {sorted(parts)}")
        records = parse_xml_volume(vol, parts)

        if not records:
            print(f"  No records from XML — trying .txt fallback for parts {sorted(parts)}")
            for part in sorted(parts):
                txt_records = parse_txt_fallback(part, PARTS_CONFIG[part])
                print(f"    Part {part} .txt: {len(txt_records)} sections")
                for r in txt_records:
                    if r["id"] not in seen_ids:
                        all_records.append(r)
                        seen_ids.add(r["id"])
        else:
            # Group by part for reporting
            from collections import Counter
            by_part = Counter(r["part"] for r in records)
            for part, count in sorted(by_part.items()):
                print(f"  Part {part}: {count} sections")
            for r in records:
                if r["id"] not in seen_ids:
                    all_records.append(r)
                    seen_ids.add(r["id"])

    print(f"\nTotal sections: {len(all_records)}")

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Written to {OUTPUT_PATH}")

    # Summary
    from collections import Counter
    by_part = Counter(r["part"] for r in all_records)
    print("\nSections per part:")
    for part, count in sorted(by_part.items(), key=lambda x: int(x[0])):
        desc = PARTS_CONFIG[part]["description"]
        print(f"  Part {part:>4} ({desc[:40]}): {count} sections")


if __name__ == "__main__":
    main()
