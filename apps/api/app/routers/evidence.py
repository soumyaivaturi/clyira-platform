"""
Evidence Fabric Router — CSV/Excel intake, entity tagging, and cross-reference.
Implements Layers 1-4 of the Evidence Fabric architecture.

Fixes vs the original stub:
  - Full row set stored in evidence_imports.raw_rows at upload time
  - /map re-processes all stored rows (not just the 5-row preview)
  - Excel (.xlsx/.xls) supported via openpyxl
  - /stats and /gaps/{assessment_id} endpoints added
"""
import csv
import io
import json
import logging
import re
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.assessment import Assessment, Finding
from app.models.base import generate_uuid
from app.models.document import Document
from app.models.evidence import EvidenceImport, EvidenceObject
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ROWS = 5000
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

SUPPORTED_ENTITY_TYPES = [
    "deviation", "oos", "training", "equipment", "material",
    "pm", "change_control", "em_excursion", "complaint", "batch_record",
]

SIGNAL_COLUMN_HINTS = {
    "deviation":      ["deviation", "dev", "nc", "nonconformance", "event"],
    "oos":            ["oos", "out of spec", "ooc", "result", "assay"],
    "training":       ["training", "course", "completion", "employee", "personnel"],
    "equipment":      ["equipment", "instrument", "asset", "calibration", "pm"],
    "material":       ["material", "batch", "lot", "supplier", "raw material"],
    "em_excursion":   ["environmental", "em ", "excursion", "viable", "bioburden"],
    "change_control": ["change control", "change request", "cr number"],
    "complaint":      ["complaint", "return", "adverse event"],
}

# Keywords used for cross-reference gap detection (entity type → finding text patterns)
ENTITY_SIGNAL_KEYWORDS: dict[str, list[str]] = {
    "equipment":      ["equipment", "instrument", "hplc", "gc ", "balance", "calibration", "iq ", "oq ", "pq "],
    "training":       ["training", "trained", "qualification of personnel", "analyst qualification"],
    "deviation":      ["deviation", "non-conformance", "investigation", "root cause", "capa"],
    "oos":            ["out-of-specification", "oos", "ooc", "out of trend", "retest", "invalidat"],
    "material":       ["raw material", "batch", "lot number", "component", "supplier"],
    "em_excursion":   ["environmental monitoring", "em excursion", "bioburden", "endotoxin"],
    "pm":             ["preventive maintenance", "pm overdue", "maintenance"],
    "change_control": ["change control", "change management"],
}


# ── Parsers ───────────────────────────────────────────────────────────────────

def _detect_entity_type(headers: list[str]) -> Optional[str]:
    headers_lower = [h.lower() for h in headers]
    for etype, hints in SIGNAL_COLUMN_HINTS.items():
        if any(any(hint in h for hint in hints) for h in headers_lower):
            return etype
    return None


def _parse_csv(content: bytes) -> tuple[list[str], list[dict]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    rows = [dict(row) for i, row in enumerate(reader) if i < MAX_ROWS]
    return headers, rows


def _parse_excel(content: bytes) -> tuple[list[str], list[dict]]:
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=422,
            detail="Excel support requires openpyxl. Install it with: pip install openpyxl",
        )
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers_raw = next(rows_iter, None)
    if not headers_raw:
        return [], []
    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(headers_raw)]
    rows = []
    for i, row in enumerate(rows_iter):
        if i >= MAX_ROWS:
            break
        rows.append({headers[j]: (str(v).strip() if v is not None else "") for j, v in enumerate(row)})
    wb.close()
    return headers, rows


def _parse_file(filename: str, content: bytes) -> tuple[list[str], list[dict]]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("xlsx", "xls"):
        return _parse_excel(content)
    if ext in ("csv", "tsv", "txt"):
        return _parse_csv(content)
    raise HTTPException(status_code=422, detail=f"Unsupported file type '.{ext}'. Use CSV, TSV, or XLSX.")


def _normalize_row(row: dict, column_mapping: dict) -> dict:
    return {field: row[col] for col, field in column_mapping.items() if col in row and field != "_skip"}


def _build_evidence_object(row: dict, normalized: dict, imp: EvidenceImport) -> EvidenceObject:
    return EvidenceObject(
        id=generate_uuid(),
        import_id=imp.id,
        company_id=imp.company_id,
        entity_type=imp.entity_type,
        entity_id=(
            normalized.get("entity_id")
            or normalized.get("equipment_id")
            or normalized.get("batch_number")
        ),
        entity_name=normalized.get("entity_name") or normalized.get("analyst"),
        signal_type=normalized.get("signal_type") or imp.entity_type,
        event_date=normalized.get("event_date"),
        severity=normalized.get("severity"),
        raw_row=row,
        normalized=normalized,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import", status_code=201)
async def import_evidence(
    file: UploadFile = File(...),
    source_system: str = Form("manual"),
    entity_type: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload CSV or Excel. Stores parsed rows; returns preview + detected columns."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=422, detail="File too large (max 10 MB)")

    try:
        headers, rows = _parse_file(file.filename, content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    if not headers:
        raise HTTPException(status_code=422, detail="File has no column headers")

    detected_type = entity_type or _detect_entity_type(headers)

    imp = EvidenceImport(
        id=generate_uuid(),
        company_id=current_user.company_id,
        uploaded_by=current_user.id,
        filename=file.filename,
        source_system=source_system,
        record_count=len(rows),
        status="ready",
        detected_columns=headers,
        entity_type=detected_type,
        column_mapping={},
        raw_rows=rows,  # store ALL rows for re-ingest at /map
    )
    db.add(imp)
    await db.commit()
    await db.refresh(imp)

    return {
        "import_id": imp.id,
        "filename": imp.filename,
        "record_count": imp.record_count,
        "detected_columns": imp.detected_columns,
        "detected_entity_type": imp.entity_type,
        "status": imp.status,
        "preview": rows[:5],
    }


class ColumnMappingRequest(BaseModel):
    entity_type: str
    column_mapping: dict  # {"CSV Column": "field_name"}


@router.post("/import/{import_id}/map", status_code=200)
async def map_columns_and_ingest(
    import_id: str,
    data: ColumnMappingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply column mapping and ingest ALL stored rows as EvidenceObjects."""
    imp = await db.get(EvidenceImport, import_id)
    if not imp or imp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Import not found")

    if data.entity_type not in SUPPORTED_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"entity_type must be one of: {', '.join(SUPPORTED_ENTITY_TYPES)}",
        )

    clean_mapping = {col: field for col, field in data.column_mapping.items() if field != "_skip"}
    if not clean_mapping:
        raise HTTPException(status_code=422, detail="Map at least one column to a field")

    # Delete any previously created objects for this import
    await db.execute(
        delete(EvidenceObject).where(EvidenceObject.import_id == import_id)
    )

    imp.entity_type = data.entity_type
    imp.column_mapping = data.column_mapping
    imp.status = "processing"
    await db.flush()

    # Re-ingest ALL stored rows using the confirmed mapping
    rows = imp.raw_rows or []
    created = 0
    for row in rows:
        normalized = _normalize_row(row, clean_mapping)
        obj = _build_evidence_object(row, normalized, imp)
        db.add(obj)
        created += 1
        if created % 500 == 0:
            await db.flush()

    imp.record_count = created
    imp.status = "ready"
    await db.commit()

    return {
        "import_id": import_id,
        "entity_type": data.entity_type,
        "column_mapping": clean_mapping,
        "objects_created": created,
        "status": "ready",
    }


@router.get("/imports", status_code=200)
async def list_imports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvidenceImport)
        .where(EvidenceImport.company_id == current_user.company_id)
        .order_by(EvidenceImport.created_at.desc())
        .limit(100)
    )
    imports = result.scalars().all()
    return {
        "imports": [
            {
                "id": i.id,
                "filename": i.filename,
                "source_system": i.source_system,
                "entity_type": i.entity_type,
                "record_count": i.record_count,
                "status": i.status,
                "detected_columns": i.detected_columns,
                "column_mapping": i.column_mapping,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in imports
        ]
    }


@router.get("/imports/{import_id}/objects", status_code=200)
async def list_objects(
    import_id: str,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    imp = await db.get(EvidenceImport, import_id)
    if not imp or imp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Import not found")

    result = await db.execute(
        select(EvidenceObject)
        .where(EvidenceObject.import_id == import_id)
        .offset(offset).limit(min(limit, 500))
    )
    objects = result.scalars().all()
    count_r = await db.execute(
        select(func.count()).select_from(EvidenceObject).where(EvidenceObject.import_id == import_id)
    )
    total = count_r.scalar() or 0

    return {
        "import_id": import_id,
        "total": total,
        "objects": [
            {
                "id": o.id,
                "entity_type": o.entity_type,
                "entity_id": o.entity_id,
                "entity_name": o.entity_name,
                "signal_type": o.signal_type,
                "event_date": o.event_date,
                "severity": o.severity,
                "normalized": o.normalized,
                "raw_row": o.raw_row,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in objects
        ],
    }


@router.get("/stats", status_code=200)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summary counts for the Evidence Fabric dashboard panel."""
    # Import totals
    import_r = await db.execute(
        select(func.count(), func.sum(EvidenceImport.record_count))
        .where(EvidenceImport.company_id == current_user.company_id)
    )
    import_count, total_records = import_r.one()
    total_records = int(total_records or 0)

    # By entity type
    by_type_r = await db.execute(
        select(EvidenceObject.entity_type, func.count())
        .where(EvidenceObject.company_id == current_user.company_id)
        .group_by(EvidenceObject.entity_type)
    )
    by_entity_type = {row[0] or "unknown": row[1] for row in by_type_r.all()}

    # By signal type
    by_signal_r = await db.execute(
        select(EvidenceObject.signal_type, func.count())
        .where(EvidenceObject.company_id == current_user.company_id)
        .group_by(EvidenceObject.signal_type)
    )
    by_signal_type = {row[0] or "unknown": row[1] for row in by_signal_r.all()}

    # By source system
    by_src_r = await db.execute(
        select(EvidenceImport.source_system, func.count())
        .where(EvidenceImport.company_id == current_user.company_id)
        .group_by(EvidenceImport.source_system)
    )
    by_source = {row[0] or "manual": row[1] for row in by_src_r.all()}

    # Ready imports (column-mapped)
    ready_r = await db.execute(
        select(func.count())
        .select_from(EvidenceImport)
        .where(
            EvidenceImport.company_id == current_user.company_id,
            EvidenceImport.status == "ready",
        )
    )
    ready_count = ready_r.scalar() or 0

    return {
        "import_count": import_count,
        "total_records": total_records,
        "ready_imports": ready_count,
        "by_entity_type": by_entity_type,
        "by_signal_type": by_signal_type,
        "by_source_system": by_source,
        "entity_types_covered": list(by_entity_type.keys()),
    }


@router.get("/gaps/{assessment_id}", status_code=200)
async def get_evidence_gaps(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cross-reference an assessment's findings against the company's Evidence Fabric.

    For each finding, checks whether any EvidenceObjects match the entity type
    referenced in the finding text. Returns supported claims (evidence found) and
    unsupported claims (no evidence found) to surface documentation gaps.
    """
    # Load assessment
    assessment = await db.get(Assessment, assessment_id)
    if not assessment or assessment.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Load all findings
    findings_r = await db.execute(
        select(Finding).where(Finding.assessment_id == assessment_id)
    )
    findings = findings_r.scalars().all()

    # Load all evidence objects for this company grouped by entity_type
    objects_r = await db.execute(
        select(EvidenceObject.entity_type, EvidenceObject.entity_id, EvidenceObject.signal_type)
        .where(EvidenceObject.company_id == current_user.company_id)
    )
    evidence_rows = objects_r.all()

    # Build lookup: entity_type → set of entity_ids
    evidence_by_type: dict[str, set] = {}
    entity_type_counts: Counter = Counter()
    for etype, eid, stype in evidence_rows:
        key = etype or stype or "unknown"
        evidence_by_type.setdefault(key, set())
        if eid:
            evidence_by_type[key].add(eid.lower())
        entity_type_counts[key] += 1

    # Cross-reference each finding
    supported: list[dict] = []
    unsupported: list[dict] = []

    for f in findings:
        finding_text = f"{f.title} {f.description or ''} {f.evidence or ''}".lower()

        matched_types: list[str] = []
        for etype, keywords in ENTITY_SIGNAL_KEYWORDS.items():
            if any(kw in finding_text for kw in keywords):
                matched_types.append(etype)

        if not matched_types:
            continue  # finding doesn't reference any traceable entity type

        evidence_count = sum(entity_type_counts.get(et, 0) for et in matched_types)

        entry = {
            "finding_id": f.id,
            "finding_title": f.title,
            "severity": f.severity,
            "level": f.level,
            "matched_entity_types": matched_types,
            "evidence_records_found": evidence_count,
        }

        if evidence_count > 0:
            supported.append(entry)
        else:
            unsupported.append(entry)

    # Entity type coverage summary
    all_entity_types = list(ENTITY_SIGNAL_KEYWORDS.keys())
    coverage = [
        {
            "entity_type": et,
            "has_evidence": et in evidence_by_type,
            "record_count": entity_type_counts.get(et, 0),
        }
        for et in all_entity_types
    ]

    return {
        "assessment_id": assessment_id,
        "document_name": None,  # caller can join from assessment if needed
        "total_findings_checked": len(supported) + len(unsupported),
        "supported_by_evidence": len(supported),
        "not_supported_by_evidence": len(unsupported),
        "coverage_score": round(
            len(supported) / max(len(supported) + len(unsupported), 1) * 100
        ),
        "supported": supported,
        "unsupported": unsupported,
        "entity_type_coverage": coverage,
        "total_evidence_records": len(evidence_rows),
    }


@router.delete("/imports/{import_id}", status_code=204)
async def delete_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    imp = await db.get(EvidenceImport, import_id)
    if not imp or imp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Import not found")

    await db.execute(delete(EvidenceObject).where(EvidenceObject.import_id == import_id))
    await db.delete(imp)
    await db.commit()
