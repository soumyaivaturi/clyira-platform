"""
IDP Engine — Provider-agnostic Intelligent Document Processing layer.

Phase 3: Separates extraction from assessment. Produces a standardized IDPOutput
regardless of provider (pdfplumber, AWS Textract, Google Document AI, Azure AI).

Current implementation: pdfplumber adapter (Phase 1-2 compatible).
Future adapters: add via _PROVIDER_MAP — no changes needed in calling code.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── IDPOutput schema ─────────────────────────────────────────────────────────

@dataclass
class IDPRegion:
    type: str                        # text, table, handwriting, signature, stamp, checkbox
    content: str
    confidence: float                # 0-1, normalized
    recognition_method: str          # digital, ocr, icr, iwr, manual
    bounding_box: Optional[list] = None   # [x0, y0, x1, y1]


@dataclass
class IDPTable:
    headers: list[str]
    rows: list[list[str]]
    confidence: float
    table_type: str = "other"         # ipc_results, material_list, yield_calc, equipment_log, other


@dataclass
class IDPPage:
    page_number: int
    page_type: str                   # form, narrative, table, signature, blank
    regions: list[IDPRegion] = field(default_factory=list)
    tables: list[IDPTable] = field(default_factory=list)


@dataclass
class IDPField:
    field_name: str
    field_value: str
    source_page: int
    confidence: float
    recognition_method: str
    criticality: str = "medium"       # critical, high, medium, low
    requires_human_verification: bool = False


@dataclass
class IDPSection:
    title: str
    start_page: int
    end_page: int
    content_summary: str = ""


@dataclass
class IDPMetadata:
    total_pages: int
    document_type_detected: str = ""
    scan_quality_score: Optional[float] = None
    handwriting_detected: bool = False
    table_count: int = 0
    blank_page_indices: list[int] = field(default_factory=list)
    idp_provider: str = "pdfplumber"
    provider_version: str = ""


@dataclass
class IDPOutput:
    """Standardized IDP extraction result, provider-independent."""
    pages: list[IDPPage] = field(default_factory=list)
    fields: list[IDPField] = field(default_factory=list)
    sections: list[IDPSection] = field(default_factory=list)
    metadata: IDPMetadata = field(default_factory=lambda: IDPMetadata(total_pages=0))


# ── Provider interface ────────────────────────────────────────────────────────

class IDPProvider:
    """Abstract provider — subclass and override extract()."""

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        raise NotImplementedError


class PdfplumberProvider(IDPProvider):
    """
    Phase 1-3 provider: enhanced pdfplumber extraction with page-boundary preservation,
    basic table detection, and per-page type classification.
    """

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            import pdfplumber
            import io
        except ImportError:
            logger.warning("pdfplumber not installed — returning empty IDPOutput")
            return IDPOutput(metadata=IDPMetadata(total_pages=0, idp_provider="pdfplumber"))

        output = IDPOutput()
        pages_data: list[IDPPage] = []
        all_tables: list[IDPTable] = []
        blank_pages: list[int] = []

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                output.metadata = IDPMetadata(
                    total_pages=len(pdf.pages),
                    idp_provider="pdfplumber",
                )

                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    text = page.extract_text() or ""
                    tables_raw = page.extract_tables() or []

                    # Classify page type
                    page_type = _classify_page(text, tables_raw)
                    if page_type == "blank":
                        blank_pages.append(page_num)

                    # Build regions
                    regions = [IDPRegion(
                        type="text",
                        content=text,
                        confidence=1.0 if text.strip() else 0.0,
                        recognition_method="digital",
                    )] if text.strip() else []

                    # Extract tables
                    page_tables = []
                    for tbl in tables_raw:
                        if not tbl or len(tbl) < 2:
                            continue
                        headers = [str(h or "").strip() for h in tbl[0]]
                        rows = [[str(c or "").strip() for c in row] for row in tbl[1:]]
                        idp_table = IDPTable(
                            headers=headers,
                            rows=rows,
                            confidence=0.9,
                            table_type=_classify_table(headers),
                        )
                        page_tables.append(idp_table)
                        all_tables.append(idp_table)

                    pages_data.append(IDPPage(
                        page_number=page_num,
                        page_type=page_type,
                        regions=regions,
                        tables=page_tables,
                    ))

                output.metadata.blank_page_indices = blank_pages
                output.metadata.table_count = len(all_tables)
                output.pages = pages_data

        except Exception as e:
            logger.error(f"IDPEngine pdfplumber extraction failed: {e}")

        return output


def _classify_page(text: str, tables: list) -> str:
    if not text.strip() and not tables:
        return "blank"
    if tables:
        return "table"
    t = text.lower()
    if any(kw in t for kw in ("signature", "approved by", "reviewed by", "authorized by")):
        return "signature"
    return "narrative"


def _classify_table(headers: list[str]) -> str:
    joined = " ".join(h.lower() for h in headers)
    if any(kw in joined for kw in ("yield", "theoretical", "actual")):
        return "yield_calc"
    if any(kw in joined for kw in ("material", "component", "lot", "quantity", "bom")):
        return "material_list"
    if any(kw in joined for kw in ("ipc", "in-process", "in process", "limit", "result", "specification")):
        return "ipc_results"
    if any(kw in joined for kw in ("equipment", "instrument", "calibration", "id", "serial")):
        return "equipment_log"
    return "other"


# ── Public IDPEngine class ────────────────────────────────────────────────────

_PROVIDER_MAP: dict[str, type[IDPProvider]] = {
    "pdfplumber": PdfplumberProvider,
    # "azure": AzureDocIntelligenceProvider,      # Phase 3+
    # "google": GoogleDocumentAIProvider,          # Phase 3+
    # "textract": AWSTextractProvider,             # Phase 3+
}


class IDPEngine:
    """
    Provider-agnostic IDP orchestration layer.
    Usage: IDPEngine(provider="pdfplumber").extract(file_bytes, filename)
    """

    def __init__(self, provider: str = "pdfplumber"):
        provider_cls = _PROVIDER_MAP.get(provider, PdfplumberProvider)
        self._provider = provider_cls()
        self._provider_name = provider

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        """Extract structured content from document bytes. Returns IDPOutput."""
        result = self._provider.extract(file_bytes, filename)
        result.metadata.idp_provider = self._provider_name
        return result

    def extract_to_dict(self, file_bytes: bytes, filename: str) -> dict:
        """Extract and return as a JSON-serializable dict for JSONB storage."""
        output = self.extract(file_bytes, filename)
        return {
            "metadata": {
                "total_pages": output.metadata.total_pages,
                "document_type_detected": output.metadata.document_type_detected,
                "scan_quality_score": output.metadata.scan_quality_score,
                "handwriting_detected": output.metadata.handwriting_detected,
                "table_count": output.metadata.table_count,
                "blank_page_indices": output.metadata.blank_page_indices,
                "idp_provider": output.metadata.idp_provider,
            },
            "pages": [
                {
                    "page_number": p.page_number,
                    "page_type": p.page_type,
                    "regions": [
                        {"type": r.type, "confidence": r.confidence, "recognition_method": r.recognition_method}
                        for r in p.regions
                    ],
                    "tables": [
                        {"table_type": t.table_type, "headers": t.headers, "row_count": len(t.rows)}
                        for t in p.tables
                    ],
                }
                for p in output.pages
            ],
            "fields": [
                {
                    "field_name": f.field_name,
                    "field_value": f.field_value,
                    "source_page": f.source_page,
                    "confidence": f.confidence,
                    "criticality": f.criticality,
                    "requires_human_verification": f.requires_human_verification,
                }
                for f in output.fields
            ],
        }
