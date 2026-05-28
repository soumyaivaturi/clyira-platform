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

# Separators: colon, equals, pipe (pdfplumber table output uses " | "), or just whitespace after label
_SEP = r'\s*(?:[:=]|\s\|\s|:\s*)\s*'

# Date value: ISO, DD/MM/YYYY, YYYY/MM/DD, "25-Dec-2024", "March 15, 2025"
_DATE_VAL = (
    r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}'          # YYYY-MM-DD or YYYY/MM/DD
    r'|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'         # DD/MM/YYYY or MM/DD/YY
    r'|\d{1,2}-[A-Za-z]{3}-\d{4}'             # DD-Mon-YYYY  ← Catalent format
    r'|[A-Za-z]+\s+\d{1,2},?\s+\d{4})'        # "March 15, 2025"
)

# Lot / batch number
_LOT_PATTERNS = [
    # Standard: "Batch No:", "Lot Number:", "Batch #:"
    (re.compile(
        r'(?:batch|lot)\s*(?:no|number|#|id|num)\.?' + _SEP + r'([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE), 0.95, "lot/batch label + value"),
    # Catalent SupplyFlex: "Batch Record:  37040001-XBR-8-1"
    (re.compile(
        r'Batch\s+Record' + _SEP + r'([A-Z0-9][\w\-./]{2,40})',
        re.IGNORECASE), 0.95, "Catalent batch record label"),
    # Catalent "Record Number:"
    (re.compile(
        r'Record\s+Number' + _SEP + r'([A-Z0-9][\w\-./]{2,40})',
        re.IGNORECASE), 0.88, "record number label"),
    # Shorthand "Lot:" / "Batch:"
    (re.compile(
        r'(?:lot|batch)' + _SEP + r'([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE), 0.82, "lot/batch shorthand"),
    # BPN/BNO/LNO abbreviated
    (re.compile(
        r'(?:^|\n)(?:BPN|BNO|LNO)' + _SEP + r'([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE | re.MULTILINE), 0.80, "abbreviated lot label"),
]

# Product name
_PRODUCT_PATTERNS = [
    # Standard labels
    (re.compile(
        r'(?:product\s*name|drug\s*product|finished\s*product|article)' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE), 0.90, "product name label"),
    # Catalent table: "Item Description" in output materials table
    (re.compile(
        r'Item\s+Description' + _SEP + r'([A-Z0-9][A-Z0-9 \-/]{5,80})',
        re.IGNORECASE), 0.88, "Catalent item description"),
    # "Customer Protocol:" — sponsor product reference
    (re.compile(
        r'Customer\s+Protocol' + _SEP + r'([A-Z0-9][\w\-./]{2,40})',
        re.IGNORECASE), 0.75, "customer protocol label"),
    # Generic "Product:"
    (re.compile(
        r'(?:^|\n)Product' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE | re.MULTILINE), 0.82, "product label"),
    # "Customer:" as fallback (CDMO context)
    (re.compile(
        r'Customer' + _SEP + r'([A-Z][A-Z\s&]{3,60}?)(?:\n|$)',
        re.IGNORECASE), 0.65, "customer/sponsor label"),
]

# Product / item code
_CODE_PATTERNS = [
    # Standard
    (re.compile(
        r'(?:product\s*code|material\s*(?:no|number)|part\s*(?:no|number))' + _SEP + r'([A-Z0-9][\w\-./]{1,30})',
        re.IGNORECASE), 0.88, "product code label"),
    # Catalent: "Item Number:" in output materials table
    (re.compile(
        r'Item\s+Number' + _SEP + r'(\d{4,10})',
        re.IGNORECASE), 0.88, "Catalent item number"),
    # Catalent: "Project Number:"
    (re.compile(
        r'Project\s+Number' + _SEP + r'([A-Z0-9][\w\-./]{2,30})',
        re.IGNORECASE), 0.85, "Catalent project number"),
    # "Item No.:" generic
    (re.compile(
        r'Item\s*(?:no|#)' + _SEP + r'([A-Z0-9][\w\-./]{1,30})',
        re.IGNORECASE), 0.82, "item no label"),
]

# Dosage form
_FORM_PATTERNS = [
    (re.compile(
        r'(?:dosage\s*form|form|presentation|formulation)' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE), 0.85, "dosage form label"),
    # Inferred from item description: "450MG TB" → Tablet, "CAP" → Capsule, "INJ" → Injection
    (re.compile(
        r'\b(tablet|capsule|injection|solution|suspension|cream|ointment|patch|inhaler|suppository)\b',
        re.IGNORECASE), 0.60, "dosage form from description"),
]

# Batch / lot size
_SIZE_PATTERNS = [
    # Standard
    (re.compile(
        r'(?:batch\s*size|lot\s*size|theoretical\s*(?:yield|quantity)|batch\s*quantity)' + _SEP + r'([\d,]+\s*(?:units?|tablets?|capsules?|vials?|mL|L|kg|g|pcs|doses?)?)',
        re.IGNORECASE), 0.88, "batch size label"),
    # Catalent: "Planned Output Quantity" in table
    (re.compile(
        r'Planned\s+Output\s+Quantity' + _SEP + r'([\d,]+)',
        re.IGNORECASE), 0.88, "Catalent planned output quantity"),
    # "Planned Quantity:" / "Output Quantity:"
    (re.compile(
        r'(?:planned|output)\s+quantity' + _SEP + r'([\d,]+\s*(?:units?|tablets?|capsules?|vials?)?)',
        re.IGNORECASE), 0.82, "planned/output quantity"),
]

# Manufacturing site
_SITE_PATTERNS = [
    # Standard
    (re.compile(
        r'(?:manufacturing\s*site|mfg\s*site|manufacture[rd]\s*(?:at|by)|site\s*(?:name|code|address))' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE), 0.88, "manufacturing site label"),
    # Catalent: "Catalent Site:  Philadelphia"
    (re.compile(
        r'Catalent\s+Site' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE), 0.92, "Catalent site label"),
    # Generic facility/plant
    (re.compile(
        r'(?:facility|plant|location)' + _SEP + r'(.+?)(?:\n|$)',
        re.IGNORECASE), 0.75, "facility label"),
]

# Manufacturing date
_DATE_PATTERNS = [
    (re.compile(
        r'(?:manufacturing\s*date|mfg\.?\s*date|date\s*of\s*manufacture|manufacture\s*date|start\s*date|production\s*date)' + _SEP + _DATE_VAL,
        re.IGNORECASE), 0.90, "manufacturing date label"),
    # Catalent "Effective Date:" on batch record cover
    (re.compile(
        r'Effective\s+Date' + _SEP + _DATE_VAL,
        re.IGNORECASE), 0.80, "effective date label"),
    (re.compile(
        r'(?:mfg|manufactured)' + _SEP + r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        re.IGNORECASE), 0.80, "mfg date shorthand"),
]

# Target release date
_RELEASE_DATE_PATTERNS = [
    (re.compile(
        r'(?:target\s*release\s*date|release\s*date|use\s*by\s*date)' + _SEP + _DATE_VAL,
        re.IGNORECASE), 0.88, "release date label"),
    # Catalent: "Expiry Date:" in output materials table
    (re.compile(
        r'Expiry\s+Date' + _SEP + _DATE_VAL,
        re.IGNORECASE), 0.88, "Catalent expiry date"),
    # Generic exp/expiration
    (re.compile(
        r'exp(?:iry|iration)?\s*date' + _SEP + _DATE_VAL,
        re.IGNORECASE), 0.85, "expiry date label"),
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
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    # Already ISO
    if re.match(r'^\d{4}-\d{2}-\d{2}$', raw):
        return raw
    # YYYY/MM/DD
    m = re.match(r'^(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})$', raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    # DD-Mon-YYYY  ← Catalent format e.g. "25-Dec-2024", "20-Feb-2028"
    m = re.match(r'^(\d{1,2})-([A-Za-z]{3})-(\d{4})$', raw)
    if m:
        mon = months.get(m.group(2).lower())
        if mon:
            return f"{m.group(3)}-{str(mon).zfill(2)}-{m.group(1).zfill(2)}"
    # DD/MM/YYYY or MM/DD/YYYY (heuristic: if first number > 12 it's DD/MM)
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', raw)
    if m:
        a, b, year = m.group(1), m.group(2), m.group(3)
        if int(a) > 12:
            return f"{year}-{b.zfill(2)}-{a.zfill(2)}"
        return f"{year}-{a.zfill(2)}-{b.zfill(2)}"
    # "March 15, 2025" or "15 March 2025"
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
