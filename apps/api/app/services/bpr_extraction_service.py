"""
BPR Field Extraction Service.

Extracts structured header fields from batch/lot production record text:
lot_number, manufacturing_date, manufacturing_site, product_name,
product_code, batch_size, dosage_form.

Used to pre-fill the New Dossier form when a user uploads a BPR document.
Returns each field with a confidence score (0-1) so the UI can highlight
low-confidence extractions for user verification.
"""
import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedBPRField:
    value: str
    confidence: float        # 0-1
    source_pattern: str      # human-readable description of what matched


@dataclass
class ExtractedBPRFields:
    lot_number: Optional[ExtractedBPRField] = None
    product_name: Optional[ExtractedBPRField] = None
    product_code: Optional[ExtractedBPRField] = None
    dosage_form: Optional[ExtractedBPRField] = None
    batch_size: Optional[ExtractedBPRField] = None
    manufacturing_site: Optional[ExtractedBPRField] = None
    manufacturing_date: Optional[ExtractedBPRField] = None
    target_release_date: Optional[ExtractedBPRField] = None

    def to_form_dict(self) -> dict:
        """Return plain values for form pre-fill, None for unextracted fields."""
        return {
            k: (v.value if v else None)
            for k, v in asdict(self).items()
            if k != "to_form_dict"
        }

    def to_confidence_dict(self) -> dict:
        """Return confidence scores keyed by field name."""
        return {
            k: (v["confidence"] if v else None)
            for k, v in asdict(self).items()
        }


# ── Regex patterns ────────────────────────────────────────────────────────────

# Lot / batch number
_LOT_PATTERNS = [
    (re.compile(
        r'(?:batch|lot)\s*(?:no|number|#|id|num)\.?\s*[:=]\s*([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE), 0.95, "lot/batch label + value"),
    (re.compile(
        r'(?:lot|batch)\s*[:=]\s*([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE), 0.85, "lot/batch shorthand"),
    (re.compile(
        r'(?:^|\n)(?:BPN|BNO|LNO)\s*[:=]\s*([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE | re.MULTILINE), 0.80, "abbreviated lot label"),
]

# Product name
_PRODUCT_PATTERNS = [
    (re.compile(
        r'(?:product\s*name|drug\s*product|finished\s*product|article)\s*[:=]\s*(.+?)(?:\n|$)',
        re.IGNORECASE), 0.90, "product name label"),
    (re.compile(
        r'(?:^|\n)Product\s*[:=]\s*(.+?)(?:\n|$)',
        re.IGNORECASE | re.MULTILINE), 0.85, "product label"),
]

# Product / item code
_CODE_PATTERNS = [
    (re.compile(
        r'(?:product\s*code|item\s*(?:no|number|code)|material\s*(?:no|number)|part\s*(?:no|number))\s*[:=]\s*([A-Z0-9][\w\-./]{1,30})',
        re.IGNORECASE), 0.88, "product code label"),
]

# Dosage form
_FORM_PATTERNS = [
    (re.compile(
        r'(?:dosage\s*form|form|presentation|formulation)\s*[:=]\s*(.+?)(?:\n|$)',
        re.IGNORECASE), 0.85, "dosage form label"),
]

# Batch / lot size
_SIZE_PATTERNS = [
    (re.compile(
        r'(?:batch\s*size|lot\s*size|theoretical\s*(?:yield|quantity)|batch\s*quantity)\s*[:=]\s*([\d,]+\s*(?:units?|tablets?|capsules?|vials?|mL|L|kg|g|pcs|doses?)?)',
        re.IGNORECASE), 0.88, "batch size label"),
]

# Manufacturing site
_SITE_PATTERNS = [
    (re.compile(
        r'(?:manufacturing\s*site|mfg\s*site|manufacture[rd]\s*(?:at|by)|site\s*(?:name|code|address))\s*[:=]\s*(.+?)(?:\n|$)',
        re.IGNORECASE), 0.88, "manufacturing site label"),
    (re.compile(
        r'(?:facility|plant|location)\s*[:=]\s*(.+?)(?:\n|$)',
        re.IGNORECASE), 0.75, "facility label"),
]

# Manufacturing date
_DATE_PATTERNS = [
    (re.compile(
        r'(?:manufacturing\s*date|mfg\.?\s*date|date\s*of\s*manufacture|manufacture\s*date|start\s*date)\s*[:=]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        re.IGNORECASE), 0.90, "manufacturing date label"),
    (re.compile(
        r'(?:mfg|manufactured)\s*[:=]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        re.IGNORECASE), 0.80, "mfg date shorthand"),
]

# Target release date
_RELEASE_DATE_PATTERNS = [
    (re.compile(
        r'(?:target\s*release\s*date|release\s*date|exp(?:iry|iration)?\s*date|use\s*by\s*date)\s*[:=]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
        re.IGNORECASE), 0.85, "release/expiry date label"),
]


def _match_first(text: str, patterns) -> Optional[ExtractedBPRField]:
    """Try patterns in order, return first match as ExtractedBPRField."""
    for pattern, confidence, description in patterns:
        m = pattern.search(text)
        if m:
            raw = m.group(1).strip().rstrip(".,;")
            if raw and len(raw) >= 2:
                return ExtractedBPRField(value=raw, confidence=confidence, source_pattern=description)
    return None


def _normalise_date(raw: str) -> str:
    """Attempt to normalise date to YYYY-MM-DD for the date input field."""
    raw = raw.strip()
    # Already ISO
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
        return raw
    # DD/MM/YYYY or MM/DD/YYYY → try YYYY-MM-DD (assume YYYY last)
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', raw)
    if m:
        # Heuristic: if first number > 12, it's DD/MM
        a, b, year = m.group(1), m.group(2), m.group(3)
        if int(a) > 12:
            return f"{year}-{b.zfill(2)}-{a.zfill(2)}"
        return f"{year}-{a.zfill(2)}-{b.zfill(2)}"
    # YYYY/MM/DD
    m = re.match(r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$', raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    # "March 15, 2025" or "15 March 2025"
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    m = re.match(r'^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$', raw)
    if m:
        mon = months.get(m.group(1).lower()[:3])
        if mon:
            return f"{m.group(3)}-{str(mon).zfill(2)}-{m.group(2).zfill(2)}"
    return raw  # return as-is if we can't normalise


class BPRExtractionService:
    """Extract structured BPR header fields from document text."""

    def extract(self, text: str) -> ExtractedBPRFields:
        result = ExtractedBPRFields()

        result.lot_number = _match_first(text, _LOT_PATTERNS)
        result.product_name = _match_first(text, _PRODUCT_PATTERNS)
        result.product_code = _match_first(text, _CODE_PATTERNS)
        result.dosage_form = _match_first(text, _FORM_PATTERNS)
        result.batch_size = _match_first(text, _SIZE_PATTERNS)
        result.manufacturing_site = _match_first(text, _SITE_PATTERNS)

        raw_mfg_date = _match_first(text, _DATE_PATTERNS)
        if raw_mfg_date:
            result.manufacturing_date = ExtractedBPRField(
                value=_normalise_date(raw_mfg_date.value),
                confidence=raw_mfg_date.confidence,
                source_pattern=raw_mfg_date.source_pattern,
            )

        raw_release = _match_first(text, _RELEASE_DATE_PATTERNS)
        if raw_release:
            result.target_release_date = ExtractedBPRField(
                value=_normalise_date(raw_release.value),
                confidence=raw_release.confidence,
                source_pattern=raw_release.source_pattern,
            )

        logger.debug(
            "BPR extraction: lot=%s product=%s date=%s site=%s",
            result.lot_number and result.lot_number.value,
            result.product_name and result.product_name.value,
            result.manufacturing_date and result.manufacturing_date.value,
            result.manufacturing_site and result.manufacturing_site.value,
        )
        return result


# ── Template field extraction ─────────────────────────────────────────────────

_BLANK_FIELD_PATTERNS = [
    re.compile(r'^(.{3,60}?)\s*[:]\s*_{3,}', re.MULTILINE),      # "Field Name: ___"
    re.compile(r'^(.{3,60}?)\s*[:]\s*\[[\s_]*\]', re.MULTILINE),  # "Field Name: [ ]"
    re.compile(r'^(.{3,60}?)\s*[:]\s*$', re.MULTILINE),           # "Field Name:" (blank value)
]

_SPEC_LINE_PATTERNS = re.compile(
    r'(?:spec(?:ification)?|limit|range|target|acceptance\s+criteria)\s*[:=]\s*(.+)',
    re.IGNORECASE
)


def extract_template_fields(text: str) -> dict:
    """
    Analyse a blank MBR template to extract required field names and any
    in-line acceptance criteria.

    Returns:
      {
        "required_fields": ["Lot Number", "Manufacturing Date", ...],
        "acceptance_criteria": [{"field": "...", "spec": "..."}, ...],
        "section_count": int,
      }
    """
    required_fields: list[str] = []
    seen: set[str] = set()

    for pattern in _BLANK_FIELD_PATTERNS:
        for m in pattern.finditer(text):
            field_name = m.group(1).strip().rstrip(":").strip()
            # Filter out very short or very long matches, numbers-only lines
            if 3 <= len(field_name) <= 80 and not re.match(r'^\d+$', field_name):
                canonical = field_name.lower()
                if canonical not in seen:
                    seen.add(canonical)
                    required_fields.append(field_name)

    acceptance_criteria: list[dict] = []
    for m in _SPEC_LINE_PATTERNS.finditer(text):
        spec_value = m.group(1).strip()
        # Find field context — look backwards for the nearest label
        start = m.start()
        context = text[max(0, start - 100):start]
        field_ctx = context.strip().split("\n")[-1].strip().rstrip(":").strip()
        if spec_value and len(spec_value) < 100:
            acceptance_criteria.append({
                "field_context": field_ctx[-60:] if field_ctx else "",
                "spec": spec_value[:120],
            })

    # Count sections (lines that look like headers — ALL CAPS or numbered)
    section_headers = re.findall(
        r'(?:^|\n)(?:\d+[\.\)]\s+[A-Z]|[A-Z][A-Z\s]{5,50})(?=\n)',
        text
    )

    return {
        "required_fields": required_fields[:100],  # cap at 100
        "acceptance_criteria": acceptance_criteria[:50],
        "section_count": len(section_headers),
    }
