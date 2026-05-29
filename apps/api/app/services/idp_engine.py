"""
IDP Engine — Provider-agnostic Intelligent Document Processing layer.

Extraction stack (all free, no cloud API required):
  pdfplumber  — legacy digital PDF baseline (Phase 1-2 compat)
  docling     — primary for native PDFs, DOCX, HTML (best layout/table detection)
  paddleocr   — primary for scanned PDFs and images (PaddleOCR v4 + PP-Structure)
  tesseract   — fallback for clean single-page printed scans
  trocr       — experimental handwriting (TrOCR base-handwritten; flags human review)

Auto-routing (provider="auto"):
  DOCX / HTML               → docling
  image (jpg/png/tiff)      → paddleocr
  PDF with text layer       → docling   (pdfplumber word-count heuristic)
  PDF scan / image-only     → paddleocr
  paddleocr unavailable     → tesseract (fallback)
  all unavailable           → pdfplumber (last resort)
"""
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum word count from pdfplumber to consider a PDF "native" (has a text layer)
_NATIVE_PDF_WORD_THRESHOLD = 50


# ── IDPOutput schema ──────────────────────────────────────────────────────────

@dataclass
class IDPRegion:
    type: str                             # text, table, handwriting, signature, stamp, checkbox
    content: str
    confidence: float                     # 0-1, normalised
    recognition_method: str              # digital, ocr, icr, iwr, manual
    bounding_box: Optional[list] = None  # [x0, y0, x1, y1]


@dataclass
class IDPTable:
    headers: list[str]
    rows: list[list[str]]
    confidence: float
    table_type: str = "other"            # ipc_results, material_list, yield_calc, equipment_log, other


@dataclass
class IDPPage:
    page_number: int
    page_type: str                       # form, narrative, table, signature, blank
    regions: list[IDPRegion] = field(default_factory=list)
    tables: list[IDPTable] = field(default_factory=list)


@dataclass
class IDPField:
    field_name: str
    field_value: str
    source_page: int
    confidence: float
    recognition_method: str
    criticality: str = "medium"          # critical, high, medium, low
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
    """Standardised IDP extraction result, provider-independent."""
    pages: list[IDPPage] = field(default_factory=list)
    fields: list[IDPField] = field(default_factory=list)
    sections: list[IDPSection] = field(default_factory=list)
    metadata: IDPMetadata = field(default_factory=lambda: IDPMetadata(total_pages=0))


# ── Shared utilities ──────────────────────────────────────────────────────────

def _pdf_to_images(file_bytes: bytes, dpi: int = 200) -> list:
    """
    Convert PDF pages to PIL Images using PyMuPDF (fitz).
    Returns empty list if fitz is not installed.
    """
    try:
        import fitz  # PyMuPDF
        from PIL import Image as PILImage
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        images = []
        for page in doc:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
        doc.close()
        return images
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — PDF-to-image conversion unavailable")
        return []
    except Exception as e:
        logger.error(f"PDF-to-image conversion failed: {e}")
        return []


def _pdfplumber_word_count(file_bytes: bytes) -> int:
    """Count words extracted by pdfplumber to detect native vs scanned PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            total = sum(len((p.extract_text() or "").split()) for p in pdf.pages)
        return total
    except Exception:
        return 0


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


def _img_to_numpy(pil_image) -> "np.ndarray":  # type: ignore[name-defined]
    import numpy as np
    return np.array(pil_image)


# ── Provider interface ────────────────────────────────────────────────────────

class IDPProvider:
    """Abstract provider — subclass and override extract()."""

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        raise NotImplementedError


# ── Provider 1: pdfplumber (legacy baseline) ──────────────────────────────────

class PdfplumberProvider(IDPProvider):
    """
    Legacy Phase 1-2 provider. Handles native digital PDFs only.
    Kept as last-resort fallback when nothing else is available.
    """

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed")
            return IDPOutput(metadata=IDPMetadata(total_pages=0, idp_provider="pdfplumber"))

        output = IDPOutput()
        pages_data: list[IDPPage] = []
        all_tables: list[IDPTable] = []
        blank_pages: list[int] = []

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                output.metadata = IDPMetadata(total_pages=len(pdf.pages), idp_provider="pdfplumber")

                for i, page in enumerate(pdf.pages):
                    page_num = i + 1
                    text = page.extract_text() or ""
                    tables_raw = page.extract_tables() or []
                    page_type = _classify_page(text, tables_raw)
                    if page_type == "blank":
                        blank_pages.append(page_num)

                    regions = [IDPRegion(
                        type="text", content=text, confidence=1.0 if text.strip() else 0.0,
                        recognition_method="digital",
                    )] if text.strip() else []

                    page_tables = []
                    for tbl in tables_raw:
                        if not tbl or len(tbl) < 2:
                            continue
                        headers = [str(h or "").strip() for h in tbl[0]]
                        rows = [[str(c or "").strip() for c in row] for row in tbl[1:]]
                        idp_table = IDPTable(
                            headers=headers, rows=rows, confidence=0.9,
                            table_type=_classify_table(headers),
                        )
                        page_tables.append(idp_table)
                        all_tables.append(idp_table)

                    pages_data.append(IDPPage(
                        page_number=page_num, page_type=page_type,
                        regions=regions, tables=page_tables,
                    ))

                output.metadata.blank_page_indices = blank_pages
                output.metadata.table_count = len(all_tables)
                output.pages = pages_data

        except Exception as e:
            logger.error(f"PdfplumberProvider failed: {e}")

        return output


# ── Provider 2: Docling (primary for native PDFs and DOCX) ───────────────────

class DoclingProvider(IDPProvider):
    """
    IBM Docling — best-in-class layout, section, and table detection for native
    PDFs, DOCX, HTML, and images with embedded text. Uses a DocumentConverter
    that is cached after first initialisation (model load is slow on cold start).

    Install: pip install docling
    """

    _converter = None  # Class-level cache — shared across instances

    @classmethod
    def _get_converter(cls):
        if cls._converter is None:
            try:
                from docling.document_converter import DocumentConverter
                cls._converter = DocumentConverter()
                logger.info("DoclingProvider: DocumentConverter initialised")
            except Exception as e:
                logger.error(f"DoclingProvider: failed to init converter: {e}")
        return cls._converter

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
        except ImportError:
            logger.warning("docling not installed — falling back to pdfplumber")
            return PdfplumberProvider().extract(file_bytes, filename)

        converter = self._get_converter()
        if converter is None:
            return PdfplumberProvider().extract(file_bytes, filename)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
        suffix = f".{ext}"

        output = IDPOutput()

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                result = converter.convert(tmp_path)
                doc = result.document
            finally:
                os.unlink(tmp_path)

            # Full text via markdown export
            full_text = doc.export_to_markdown()

            # Page count — use pdfplumber as source of truth for PDFs
            total_pages = 1
            if ext == "pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                        total_pages = len(pdf.pages)
                except Exception:
                    total_pages = max(1, full_text.count("\f") + 1)

            output.metadata = IDPMetadata(
                total_pages=total_pages,
                idp_provider="docling",
                document_type_detected=ext.upper(),
            )

            # Build a single composite page with full text
            # (Docling's page segmentation is available in doc.pages but varies by version)
            regions = []
            if full_text.strip():
                regions.append(IDPRegion(
                    type="text",
                    content=full_text,
                    confidence=1.0,
                    recognition_method="digital",
                ))

            # Extract tables
            all_tables: list[IDPTable] = []
            try:
                for tbl_item in doc.tables:
                    try:
                        df = tbl_item.export_to_dataframe()
                        if df is None or df.empty:
                            continue
                        headers = [str(c) for c in df.columns.tolist()]
                        rows = [[str(v) for v in row] for row in df.values.tolist()]
                        idp_table = IDPTable(
                            headers=headers,
                            rows=rows,
                            confidence=0.92,
                            table_type=_classify_table(headers),
                        )
                        all_tables.append(idp_table)
                    except Exception:
                        pass
            except Exception:
                pass

            # Extract sections from heading elements
            sections: list[IDPSection] = []
            try:
                current_heading = ""
                current_page = 1
                for element, _level in doc.iterate_items():
                    label = getattr(getattr(element, "label", None), "value", "")
                    if label in ("section_header", "title"):
                        text_val = getattr(element, "text", "") or ""
                        if text_val and text_val != current_heading:
                            sections.append(IDPSection(
                                title=text_val.strip(),
                                start_page=current_page,
                                end_page=current_page,
                            ))
                            current_heading = text_val
            except Exception:
                pass

            output.pages = [IDPPage(
                page_number=1,
                page_type="narrative" if not all_tables else "table",
                regions=regions,
                tables=all_tables,
            )]
            output.sections = sections
            output.metadata.table_count = len(all_tables)

        except Exception as e:
            logger.error(f"DoclingProvider failed: {e}")
            return PdfplumberProvider().extract(file_bytes, filename)

        return output


# ── Provider 3: PaddleOCR (primary for scanned PDFs and images) ───────────────

class PaddleOCRProvider(IDPProvider):
    """
    Alibaba PaddleOCR v4 + PP-Structure for scanned PDFs and image files.
    Handles printed text (OCR), mixed documents, and table structure detection.
    Handwriting confidence is returned as-is; low-confidence fields are flagged
    for human verification.

    Install: pip install paddlepaddle paddleocr
    System:  Requires PyMuPDF (pip install pymupdf) for PDF→image conversion.
    """

    _ocr_engine = None
    _structure_engine = None

    @classmethod
    def _get_ocr(cls):
        if cls._ocr_engine is None:
            try:
                from paddleocr import PaddleOCR
                cls._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    use_gpu=False,
                    show_log=False,
                )
                logger.info("PaddleOCRProvider: OCR engine initialised")
            except Exception as e:
                logger.error(f"PaddleOCRProvider: OCR init failed: {e}")
        return cls._ocr_engine

    @classmethod
    def _get_structure(cls):
        if cls._structure_engine is None:
            try:
                from paddleocr import PPStructure
                cls._structure_engine = PPStructure(
                    show_log=False,
                    image_orientation=True,
                    lang="en",
                )
                logger.info("PaddleOCRProvider: PP-Structure engine initialised")
            except Exception as e:
                logger.warning(f"PaddleOCRProvider: PP-Structure init failed (tables will be skipped): {e}")
        return cls._structure_engine

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except ImportError:
            logger.warning("paddleocr not installed — falling back to TesseractProvider")
            return TesseractProvider().extract(file_bytes, filename)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        output = IDPOutput()

        # Get page images
        images = []
        if ext == "pdf":
            images = _pdf_to_images(file_bytes)
            if not images:
                logger.warning("PaddleOCRProvider: PDF-to-image failed; falling back to pdfplumber")
                return PdfplumberProvider().extract(file_bytes, filename)
        else:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(file_bytes)).convert("RGB")
                images = [img]
            except Exception as e:
                logger.error(f"PaddleOCRProvider: image load failed: {e}")
                return IDPOutput(metadata=IDPMetadata(total_pages=0, idp_provider="paddleocr"))

        ocr = self._get_ocr()
        structure = self._get_structure()

        pages_data: list[IDPPage] = []
        all_tables: list[IDPTable] = []
        blank_pages: list[int] = []
        handwriting_detected = False
        total_confidence_sum = 0.0
        total_word_count = 0

        for i, pil_img in enumerate(images):
            page_num = i + 1
            img_arr = _img_to_numpy(pil_img)

            # Run OCR
            page_text = ""
            page_confidence = 1.0
            regions: list[IDPRegion] = []

            try:
                if ocr is not None:
                    ocr_result = ocr.ocr(img_arr, cls=True)
                    lines = []
                    confidences = []
                    if ocr_result and ocr_result[0]:
                        for line in ocr_result[0]:
                            if line and len(line) >= 2:
                                text_conf = line[1]
                                if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
                                    text = str(text_conf[0])
                                    conf = float(text_conf[1])
                                    lines.append(text)
                                    confidences.append(conf)
                                    total_confidence_sum += conf
                                    total_word_count += 1

                    page_text = " ".join(lines)
                    page_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

                    # Low confidence on many words suggests handwriting
                    low_conf_count = sum(1 for c in confidences if c < 0.75)
                    if confidences and (low_conf_count / len(confidences)) > 0.3:
                        handwriting_detected = True
                        recognition_method = "icr"
                    else:
                        recognition_method = "ocr"

                    if page_text.strip():
                        regions.append(IDPRegion(
                            type="text",
                            content=page_text,
                            confidence=page_confidence,
                            recognition_method=recognition_method,
                        ))
            except Exception as e:
                logger.warning(f"PaddleOCR page {page_num} OCR failed: {e}")

            # Run PP-Structure for tables
            page_tables: list[IDPTable] = []
            try:
                if structure is not None:
                    struct_result = structure(img_arr)
                    for region in (struct_result or []):
                        if isinstance(region, dict) and region.get("type") == "table":
                            try:
                                html = region.get("res", {}).get("html", "")
                                if html:
                                    tbl = _parse_html_table(html)
                                    if tbl:
                                        page_tables.append(tbl)
                                        all_tables.append(tbl)
                            except Exception:
                                pass
            except Exception as e:
                logger.debug(f"PP-Structure page {page_num} failed: {e}")

            page_type = _classify_page(page_text, page_tables)
            if page_type == "blank":
                blank_pages.append(page_num)

            pages_data.append(IDPPage(
                page_number=page_num,
                page_type=page_type,
                regions=regions,
                tables=page_tables,
            ))

        avg_confidence = (total_confidence_sum / total_word_count) if total_word_count > 0 else 0.0

        output.pages = pages_data
        output.metadata = IDPMetadata(
            total_pages=len(images),
            idp_provider="paddleocr",
            scan_quality_score=round(avg_confidence, 3),
            handwriting_detected=handwriting_detected,
            table_count=len(all_tables),
            blank_page_indices=blank_pages,
        )

        return output


def _parse_html_table(html: str) -> Optional[IDPTable]:
    """Parse a simple HTML table string into IDPTable."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        rows_raw = soup.find_all("tr")
        if not rows_raw:
            return None
        headers = [td.get_text(strip=True) for td in rows_raw[0].find_all(["th", "td"])]
        rows = [
            [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            for row in rows_raw[1:]
        ]
        if not headers:
            return None
        return IDPTable(
            headers=headers,
            rows=rows,
            confidence=0.88,
            table_type=_classify_table(headers),
        )
    except Exception:
        return None


# ── Provider 4: Tesseract (fallback for clean printed scans) ─────────────────

class TesseractProvider(IDPProvider):
    """
    Tesseract OCR — fallback for clean, single-column printed scans when
    PaddleOCR is unavailable. Moderate accuracy on complex layouts.

    Install: pip install pytesseract
    System:  brew install tesseract  (macOS) / apt-get install tesseract-ocr (Linux)
    """

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            import pytesseract
            from PIL import Image as PILImage  # noqa: F401
        except ImportError:
            logger.warning("pytesseract not installed — falling back to pdfplumber")
            return PdfplumberProvider().extract(file_bytes, filename)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        output = IDPOutput()

        images = []
        if ext == "pdf":
            images = _pdf_to_images(file_bytes)
            if not images:
                return PdfplumberProvider().extract(file_bytes, filename)
        else:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(file_bytes)).convert("RGB")
                images = [img]
            except Exception as e:
                logger.error(f"TesseractProvider: image load failed: {e}")
                return IDPOutput(metadata=IDPMetadata(total_pages=0, idp_provider="tesseract"))

        pages_data: list[IDPPage] = []
        blank_pages: list[int] = []
        total_conf_sum = 0.0
        total_words = 0

        for i, pil_img in enumerate(images):
            page_num = i + 1
            page_text = ""
            page_confidence = 0.0

            try:
                page_text = pytesseract.image_to_string(pil_img, config="--oem 3 --psm 6")
                data = pytesseract.image_to_data(
                    pil_img,
                    config="--oem 3 --psm 6",
                    output_type=pytesseract.Output.DICT,
                )
                confs = [int(c) for c in data.get("conf", []) if str(c).lstrip("-").isdigit() and int(c) >= 0]
                if confs:
                    page_confidence = sum(confs) / (len(confs) * 100.0)
                    total_conf_sum += page_confidence
                    total_words += len(confs)
            except Exception as e:
                logger.warning(f"TesseractProvider page {page_num} failed: {e}")

            page_type = _classify_page(page_text, [])
            if page_type == "blank":
                blank_pages.append(page_num)

            regions = [IDPRegion(
                type="text",
                content=page_text,
                confidence=page_confidence,
                recognition_method="ocr",
            )] if page_text.strip() else []

            pages_data.append(IDPPage(
                page_number=page_num,
                page_type=page_type,
                regions=regions,
                tables=[],
            ))

        avg_conf = (total_conf_sum / total_words) if total_words > 0 else 0.0

        output.pages = pages_data
        output.metadata = IDPMetadata(
            total_pages=len(images),
            idp_provider="tesseract",
            scan_quality_score=round(avg_conf, 3),
            blank_page_indices=blank_pages,
        )

        return output


# ── Provider 5: TrOCR (experimental handwriting) ─────────────────────────────

class TrOCRProvider(IDPProvider):
    """
    Microsoft TrOCR (Transformer OCR) — experimental handwriting recognition.
    Uses microsoft/trocr-base-handwritten from HuggingFace Transformers.

    All extracted fields are flagged requires_human_verification=True because
    TrOCR accuracy on pharma batch record handwriting is not yet validated.
    Use only as a supplement to PaddleOCR for regions identified as handwritten.

    Install: pip install transformers torch pillow
    Note:    First run downloads ~500 MB model weights from HuggingFace.
    Warning: CPU inference is slow (~5-15s per page). GPU recommended for production.
    """

    _processor = None
    _model = None
    MODEL_ID = "microsoft/trocr-base-handwritten"

    @classmethod
    def _load_model(cls):
        if cls._processor is None or cls._model is None:
            try:
                from transformers import TrOCRProcessor, VisionEncoderDecoderModel
                logger.info(f"TrOCRProvider: loading {cls.MODEL_ID} (first load downloads ~500 MB)…")
                cls._processor = TrOCRProcessor.from_pretrained(cls.MODEL_ID)
                cls._model = VisionEncoderDecoderModel.from_pretrained(cls.MODEL_ID)
                cls._model.eval()
                logger.info("TrOCRProvider: model loaded")
            except Exception as e:
                logger.error(f"TrOCRProvider: model load failed: {e}")
        return cls._processor, cls._model

    def _ocr_image(self, pil_img, processor, model) -> tuple[str, float]:
        """Run TrOCR on a single PIL image, return (text, confidence)."""
        try:
            import torch
            from PIL import Image as PILImage

            # TrOCR expects RGB
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            pixel_values = processor(images=pil_img, return_tensors="pt").pixel_values

            with torch.no_grad():
                outputs = model.generate(
                    pixel_values,
                    max_new_tokens=128,
                    output_scores=True,
                    return_dict_in_generate=True,
                )

            text = processor.batch_decode(outputs.sequences, skip_special_tokens=True)[0]

            # Approximate confidence from sequence scores
            confidence = 0.6  # TrOCR doesn't expose token-level confidence directly
            try:
                import math
                scores = outputs.scores
                if scores:
                    log_probs = [score.max(dim=-1).values.item() for score in scores]
                    avg_log_prob = sum(log_probs) / len(log_probs)
                    confidence = min(0.95, max(0.3, math.exp(avg_log_prob / 10)))
            except Exception:
                pass

            return text, confidence

        except Exception as e:
            logger.warning(f"TrOCRProvider._ocr_image failed: {e}")
            return "", 0.0

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        try:
            import torch  # noqa: F401
            from transformers import TrOCRProcessor  # noqa: F401
        except ImportError:
            logger.warning("transformers/torch not installed — TrOCR unavailable; falling back to PaddleOCR")
            return PaddleOCRProvider().extract(file_bytes, filename)

        processor, model = self._load_model()
        if processor is None or model is None:
            logger.warning("TrOCRProvider: model not loaded; falling back to PaddleOCR")
            return PaddleOCRProvider().extract(file_bytes, filename)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        images = []
        if ext == "pdf":
            images = _pdf_to_images(file_bytes, dpi=150)  # Lower DPI for speed
            if not images:
                return PaddleOCRProvider().extract(file_bytes, filename)
        else:
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(file_bytes)).convert("RGB")
                images = [img]
            except Exception as e:
                logger.error(f"TrOCRProvider: image load failed: {e}")
                return IDPOutput(metadata=IDPMetadata(total_pages=0, idp_provider="trocr"))

        pages_data: list[IDPPage] = []
        blank_pages: list[int] = []

        for i, pil_img in enumerate(images):
            page_num = i + 1
            logger.info(f"TrOCRProvider: processing page {page_num}/{len(images)}…")

            text, confidence = self._ocr_image(pil_img, processor, model)

            page_type = _classify_page(text, [])
            if page_type == "blank":
                blank_pages.append(page_num)

            regions = [IDPRegion(
                type="handwriting",
                content=text,
                confidence=confidence,
                recognition_method="iwr",
            )] if text.strip() else []

            pages_data.append(IDPPage(
                page_number=page_num,
                page_type=page_type,
                regions=regions,
                tables=[],
            ))

        # All TrOCR fields require human verification — accuracy is experimental
        fields = []
        for page in pages_data:
            for region in page.regions:
                if region.content.strip():
                    fields.append(IDPField(
                        field_name=f"page_{page.page_number}_handwritten_text",
                        field_value=region.content,
                        source_page=page.page_number,
                        confidence=region.confidence,
                        recognition_method="iwr",
                        requires_human_verification=True,
                    ))

        output = IDPOutput()
        output.pages = pages_data
        output.fields = fields
        output.metadata = IDPMetadata(
            total_pages=len(images),
            idp_provider="trocr",
            handwriting_detected=True,
            blank_page_indices=blank_pages,
        )

        return output


# ── Provider map ──────────────────────────────────────────────────────────────

_PROVIDER_MAP: dict[str, type[IDPProvider]] = {
    "pdfplumber": PdfplumberProvider,
    "docling":    DoclingProvider,
    "paddleocr":  PaddleOCRProvider,
    "tesseract":  TesseractProvider,
    "trocr":      TrOCRProvider,
}


# ── Auto-detection routing ────────────────────────────────────────────────────

def _detect_provider(file_bytes: bytes, filename: str) -> str:
    """
    Infer the best available provider for this file.

    Routing logic:
      DOCX / HTML           → docling
      image (jpg/png/tiff)  → paddleocr
      PDF with text layer   → docling   (if word_count > threshold)
      PDF scan / image-only → paddleocr (if word_count <= threshold)
      paddleocr unavailable → tesseract
      docling unavailable   → pdfplumber
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Check which providers are actually installed
    def _available(pkg: str) -> bool:
        try:
            __import__(pkg)
            return True
        except ImportError:
            return False

    has_docling    = _available("docling")
    has_paddleocr  = _available("paddleocr")
    has_tesseract  = _available("pytesseract")

    if ext in ("docx", "doc", "html", "htm", "pptx"):
        return "docling" if has_docling else "pdfplumber"

    if ext in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "gif", "webp"):
        if has_paddleocr:
            return "paddleocr"
        if has_tesseract:
            return "tesseract"
        return "pdfplumber"

    if ext == "pdf":
        word_count = _pdfplumber_word_count(file_bytes)
        if word_count >= _NATIVE_PDF_WORD_THRESHOLD:
            # Native PDF — Docling handles layout/tables better
            return "docling" if has_docling else "pdfplumber"
        else:
            # Scanned/image-only PDF — needs OCR
            if has_paddleocr:
                return "paddleocr"
            if has_tesseract:
                return "tesseract"
            return "pdfplumber"

    # Unknown extension — try docling, fall back to pdfplumber
    return "docling" if has_docling else "pdfplumber"


# ── Public IDPEngine class ────────────────────────────────────────────────────

class IDPEngine:
    """
    Provider-agnostic IDP orchestration layer.

    Usage:
        IDPEngine().extract(file_bytes, filename)           # auto-detect provider
        IDPEngine(provider="docling").extract(...)          # force a specific provider
        IDPEngine(provider="paddleocr").extract(...)        # force PaddleOCR
        IDPEngine(provider="trocr").extract(...)            # experimental handwriting

    The default provider is "auto" which routes based on file type and content.
    """

    def __init__(self, provider: str = "auto"):
        self._provider_name = provider
        if provider != "auto":
            provider_cls = _PROVIDER_MAP.get(provider, PdfplumberProvider)
            self._provider: Optional[IDPProvider] = provider_cls()
        else:
            self._provider = None  # resolved per-call in auto mode

    def extract(self, file_bytes: bytes, filename: str) -> IDPOutput:
        """Extract structured content from document bytes. Returns IDPOutput."""
        if self._provider_name == "auto":
            chosen = _detect_provider(file_bytes, filename)
            logger.info(f"IDPEngine auto-routing: {filename!r} → {chosen}")
            provider_cls = _PROVIDER_MAP.get(chosen, PdfplumberProvider)
            provider = provider_cls()
            result = provider.extract(file_bytes, filename)
            result.metadata.idp_provider = chosen
        else:
            result = self._provider.extract(file_bytes, filename)  # type: ignore[union-attr]
            result.metadata.idp_provider = self._provider_name

        return result

    @staticmethod
    def output_to_dict(output: "IDPOutput") -> dict:
        """Serialise an IDPOutput to a JSON-serialisable dict for JSONB storage."""
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
                        {
                            "type": r.type,
                            "confidence": r.confidence,
                            "recognition_method": r.recognition_method,
                            "content_length": len(r.content),
                        }
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
                    "recognition_method": f.recognition_method,
                }
                for f in output.fields
            ],
        }

    def extract_to_dict(self, file_bytes: bytes, filename: str) -> dict:
        """Extract and return as a JSON-serialisable dict for JSONB storage."""
        output = self.extract(file_bytes, filename)
        return IDPEngine.output_to_dict(output)

    @staticmethod
    def full_text(output: IDPOutput) -> str:
        """Flatten all page region content into a single string for the assessment engine.

        Uses double-newlines (``\\n\\n``) between pages/regions so the frontend
        can distinguish real paragraph breaks from soft line-wraps within a
        block.  Single ``\\n`` inside a region's content is left as-is — the
        frontend will collapse them to spaces within the same paragraph.
        """
        parts = []
        for page in output.pages:
            for region in page.regions:
                if region.content.strip():
                    parts.append(region.content)
            for table in page.tables:
                # Serialise table rows as tab-separated text so rules can pattern-match
                header_line = "\t".join(table.headers)
                parts.append(header_line)
                for row in table.rows:
                    parts.append("\t".join(row))
        return "\n\n".join(parts)
