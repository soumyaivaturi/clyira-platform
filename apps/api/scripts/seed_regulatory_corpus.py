"""
seed_regulatory_corpus.py — Build regulatory JSONL indexes from source files.

Outputs to apps/api/rag_index/:
  regulatory_corpus.jsonl  — 21 CFR sections (replaces existing 222-record file)
  ich_guidelines.jsonl     — ICH Q/E/S guideline chunks
  eu_gmp.jsonl             — EU GMP chapter + annex chunks

Run from apps/api/:
    python scripts/seed_regulatory_corpus.py
"""
import json
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    sys.exit("pdfplumber required: pip install pdfplumber")

# ── Paths ─────────────────────────────────────────────────────────────────────

CORPUS_DIR = Path(__file__).parent.parent.parent.parent.parent / "Clyira-Corpus"
RAG_DIR    = Path(__file__).parent.parent / "rag_index"

CFR_DIR    = CORPUS_DIR / "02-Regulatory" / "21-CFR"
ICH_DIR    = CORPUS_DIR / "02-Regulatory" / "ICH"
EU_GMP_DIR = CORPUS_DIR / "02-Regulatory" / "EU-GMP"

# ── CFR part metadata ─────────────────────────────────────────────────────────

_CFR_META = {
    "4":   ("General",                        ["SOP", "CAPA"]),
    "11":  ("Electronic Records",             ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation", "MBR", "QC_TEST"]),
    "58":  ("GLP",                            ["LIR", "Validation"]),
    "210": ("Drug GMP — General",             ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation", "MBR", "QC_TEST"]),
    "211": ("Drug GMP — Finished Pharma",     ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation", "MBR", "QC_TEST"]),
    "212": ("PET Drug GMP",                   ["ATM", "Validation"]),
    "600": ("Biologics — General",            ["SOP", "CAPA", "Deviation", "Validation"]),
    "601": ("Biologics — Licensing",          ["SOP", "CAPA", "Validation"]),
    "606": ("Blood — cGMP",                   ["SOP", "CAPA", "LIR", "ATM"]),
    "610": ("Biologics — General Standards",  ["SOP", "LIR", "ATM"]),
    "630": ("Blood Donor Eligibility",        ["LIR", "ATM"]),
    "640": ("Blood Components",               ["LIR", "ATM", "MBR"]),
    "660": ("Diagnostics",                    ["ATM", "Validation"]),
    "680": ("Allergenic Products",            ["ATM"]),
    "820": ("Medical Device QSR/QMSR",        ["SOP", "CAPA", "Deviation", "Validation"]),
}


# ── CFR parser ────────────────────────────────────────────────────────────────

_SECTION_RE = re.compile(r'^§\s+(\d+\.\d+)\s+(.*)')
_SKIP_RE    = re.compile(r'^={3,}|^-{3,}|^Authority:|^Source:|^\[')


def _parse_cfr_file(path: Path) -> list[dict]:
    """Parse a 21 CFR .txt file into one record per section."""
    part = None
    for stem in path.stem.split("_"):
        if stem.isdigit():
            part = stem
            break
    if not part or part not in _CFR_META:
        return []

    part_desc, doc_cats = _CFR_META[part]
    records = []
    current_section = None
    current_title   = ""
    current_lines   = []

    def _flush():
        if current_section and current_lines:
            text = " ".join(current_lines).strip()
            if len(text) > 40:
                records.append({
                    "id":                  f"21cfr-{part}-{current_section.replace('.', '-')}",
                    "citation_reference":  f"21 CFR {current_section}",
                    "section":             current_section,
                    "part":                part,
                    "title":               current_title,
                    "content":             text,
                    "agency":              "FDA",
                    "document_type":       "regulation",
                    "source_body":         "FDA/eCFR",
                    "hierarchy_level":     "section",
                    "document_categories": doc_cats,
                    "part_description":    part_desc,
                    "is_current":          True,
                    "source":              "ecfr.gov",
                })

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or _SKIP_RE.match(line):
            continue
        m = _SECTION_RE.match(line)
        if m:
            _flush()
            current_section = m.group(1)
            current_title   = m.group(2).strip(" .-")
            current_lines   = []
        elif current_section:
            # Strip citation footnotes like [43 FR 45077, ...]
            clean = re.sub(r'\[\d+ FR \d+.*?\]', '', line).strip()
            if clean:
                current_lines.append(clean)

    _flush()
    return records


# ── PDF chunker ───────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks on sentence boundaries."""
    text = re.sub(r'\s+', ' ', text).strip()
    chunks = []
    start  = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at sentence boundary
        if end < len(text):
            boundary = max(
                text.rfind('. ', start, end),
                text.rfind('.\n', start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if len(chunk) > 80:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else end
    return chunks


def _extract_pdf_text(path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
    except Exception as e:
        print(f"  WARNING: could not read {path.name}: {e}")
    return "\n".join(pages)


def _pdf_to_records(
    path: Path,
    source_id_prefix: str,
    citation_prefix: str,
    source_body: str,
    doc_categories: list[str],
) -> list[dict]:
    """Convert a PDF file into chunked JSONL records."""
    text = _extract_pdf_text(path)
    if not text.strip():
        print(f"  WARNING: no text extracted from {path.name}")
        return []

    stem = path.stem  # e.g. "ICH-Q7" or "EU-GMP-Chapter-4"
    chunks = _chunk_text(text)
    records = []
    for i, chunk in enumerate(chunks):
        records.append({
            "id":                  f"{source_id_prefix}-{stem}-{i+1:03d}",
            "citation_reference":  f"{citation_prefix} — {stem.replace('-', ' ')}",
            "title":               stem.replace("-", " "),
            "text":                chunk,
            "source_body":         source_body,
            "document_categories": doc_categories,
            "source_file":         path.name,
            "chunk_index":         i + 1,
        })
    return records


# ── ICH guideline metadata ────────────────────────────────────────────────────

_ICH_DOC_CATS = {
    # Q-series (Quality) — most relevant to Clyira
    "Q1":  ["Validation", "ATM"],
    "Q2":  ["ATM", "Validation"],
    "Q3":  ["ATM", "Validation"],
    "Q4":  ["ATM"],
    "Q5":  ["Validation", "SOP"],
    "Q6":  ["ATM", "LIR"],
    "Q7":  ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation", "MBR"],
    "Q8":  ["Validation", "SOP"],
    "Q9":  ["CAPA", "Deviation", "SOP", "Validation"],
    "Q10": ["SOP", "CAPA", "Deviation", "Validation"],
    "Q11": ["Validation", "SOP"],
    "Q12": ["CAPA", "Deviation", "SOP"],
    "Q13": ["Validation", "MBR"],
    "Q14": ["ATM", "Validation"],
    # E-series (Clinical / Safety) — relevant to CAPA/Deviation
    "E2":  ["CAPA", "Deviation"],
    "E3":  ["SOP"],
    "E6":  ["SOP", "CAPA"],
    "E9":  ["Validation", "LIR"],
    # S-series (Safety/Tox) — validation focus
    "S":   ["Validation"],
}

def _get_ich_cats(filename: str) -> list[str]:
    stem = Path(filename).stem.upper()  # e.g. Q7, Q10, E6R2
    for prefix, cats in _ICH_DOC_CATS.items():
        if stem.startswith(prefix):
            return cats
    return ["SOP", "CAPA", "Validation"]  # default


# ── Main ──────────────────────────────────────────────────────────────────────

def build_cfr(out_path: Path):
    print("\n=== Building regulatory_corpus.jsonl (21 CFR sections) ===")
    all_records = []
    for txt in sorted(CFR_DIR.glob("*.txt")):
        if "Index" in txt.name:
            continue
        recs = _parse_cfr_file(txt)
        print(f"  {txt.name}: {len(recs)} sections")
        all_records.extend(recs)

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec) + "\n")
    print(f"  → {len(all_records)} total records written to {out_path.name}")


def build_ich(out_path: Path):
    print("\n=== Building ich_guidelines.jsonl ===")
    all_records = []
    for pdf in sorted(ICH_DIR.rglob("*.pdf")):
        cats = _get_ich_cats(pdf.name)
        recs = _pdf_to_records(
            path=pdf,
            source_id_prefix="ich",
            citation_prefix="ICH",
            source_body="ICH",
            doc_categories=cats,
        )
        print(f"  {pdf.name}: {len(recs)} chunks")
        all_records.extend(recs)

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec) + "\n")
    print(f"  → {len(all_records)} total records written to {out_path.name}")


def build_eu_gmp(out_path: Path):
    print("\n=== Building eu_gmp.jsonl ===")
    all_records = []

    # All doc types — EU GMP is cross-cutting
    eu_all_cats = ["SOP", "CAPA", "Deviation", "LIR", "ATM", "Validation", "MBR", "QC_TEST"]

    for pdf in sorted(EU_GMP_DIR.rglob("*.pdf")):
        recs = _pdf_to_records(
            path=pdf,
            source_id_prefix="eu-gmp",
            citation_prefix="EU GMP",
            source_body="EMA/EU GMP",
            doc_categories=eu_all_cats,
        )
        print(f"  {pdf.name}: {len(recs)} chunks")
        all_records.extend(recs)

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec) + "\n")
    print(f"  → {len(all_records)} total records written to {out_path.name}")


if __name__ == "__main__":
    RAG_DIR.mkdir(exist_ok=True)

    if not CORPUS_DIR.exists():
        sys.exit(f"Corpus not found at {CORPUS_DIR}\nUpdate CORPUS_DIR in this script.")

    build_cfr(RAG_DIR / "regulatory_corpus.jsonl")
    build_ich(RAG_DIR / "ich_guidelines.jsonl")
    build_eu_gmp(RAG_DIR / "eu_gmp.jsonl")

    print("\nDone. Restart the API to pick up the new indexes.")
