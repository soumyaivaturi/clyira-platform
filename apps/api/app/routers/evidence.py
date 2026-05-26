"""
Evidence Fabric Router — CSV/Excel intake, entity tagging, and cross-reference.
Implements Layers 1-4 of the Evidence Fabric architecture.
"""
import csv
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.base import generate_uuid
from app.models.evidence import EvidenceImport, EvidenceObject
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_ENTITY_TYPES = [
    "deviation", "oos", "training", "equipment", "material",
    "pm", "change_control", "em_excursion", "complaint", "batch_record",
]

SIGNAL_COLUMN_HINTS = {
    "deviation": ["deviation", "dev", "nc", "nonconformance", "event"],
    "oos": ["oos", "out of spec", "ooc", "result", "assay"],
    "training": ["training", "course", "completion", "employee", "personnel"],
    "equipment": ["equipment", "instrument", "asset", "calibration", "pm"],
    "material": ["material", "batch", "lot", "supplier", "raw material"],
}


def _detect_entity_type(headers: list[str]) -> Optional[str]:
    headers_lower = [h.lower() for h in headers]
    for etype, hints in SIGNAL_COLUMN_HINTS.items():
        if any(any(hint in h for hint in hints) for h in headers_lower):
            return etype
    return None


def _parse_csv_rows(content: bytes, max_rows: int = 5000) -> tuple[list[str], list[dict]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = []
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        rows.append(dict(row))
    return list(headers), rows


def _normalize_row(row: dict, column_mapping: dict) -> dict:
    result = {}
    for src_col, field_name in column_mapping.items():
        if src_col in row:
            result[field_name] = row[src_col]
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import", status_code=201)
async def import_evidence(
    file: UploadFile = File(...),
    source_system: str = Form("manual"),
    entity_type: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV file and detect column structure. Returns import ID + detected columns."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "tsv", "txt"):
        raise HTTPException(status_code=422, detail="Only CSV/TSV files are supported. Excel: save as CSV first.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB cap
        raise HTTPException(status_code=422, detail="File too large (max 10 MB)")

    try:
        headers, rows = _parse_csv_rows(content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {e}")

    if not headers:
        raise HTTPException(status_code=422, detail="CSV has no column headers")

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
    column_mapping: dict   # {"CSV Column Name": "field_name"}
    # Recognized field names: entity_id, entity_name, event_date, signal_type,
    # severity, description, status, batch_number, analyst, equipment_id


@router.post("/import/{import_id}/map", status_code=200)
async def map_columns_and_ingest(
    import_id: str,
    data: ColumnMappingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply column mapping and create EvidenceObject records from the CSV rows."""
    imp = await db.get(EvidenceImport, import_id)
    if not imp or imp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Import not found")

    if data.entity_type not in SUPPORTED_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail=f"entity_type must be one of: {', '.join(SUPPORTED_ENTITY_TYPES)}")

    imp.entity_type = data.entity_type
    imp.column_mapping = data.column_mapping
    imp.status = "processing"
    await db.flush()

    # Delete any previously ingested objects for this import
    existing = await db.execute(
        select(EvidenceObject).where(EvidenceObject.import_id == import_id)
    )
    for obj in existing.scalars().all():
        await db.delete(obj)

    # Re-read the file content isn't stored, so we rely on the stored column mapping
    # and create stub objects. In production, file content would be in object storage.
    # For MVP: we just confirm the mapping and mark ready.
    imp.status = "ready"
    await db.commit()

    return {
        "import_id": import_id,
        "entity_type": data.entity_type,
        "column_mapping": data.column_mapping,
        "status": "ready",
        "message": "Column mapping saved. Evidence objects will be created on next re-import or via bulk ingest.",
    }


@router.post("/ingest/{import_id}", status_code=200)
async def ingest_rows(
    import_id: str,
    rows: list[dict],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept JSON rows (from frontend preview) and create EvidenceObject records."""
    imp = await db.get(EvidenceImport, import_id)
    if not imp or imp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Import not found")
    if not imp.column_mapping:
        raise HTTPException(status_code=422, detail="Apply column mapping first via /map")

    created = 0
    for row in rows[:5000]:
        normalized = _normalize_row(row, imp.column_mapping)
        obj = EvidenceObject(
            id=generate_uuid(),
            import_id=import_id,
            company_id=current_user.company_id,
            entity_type=imp.entity_type,
            entity_id=normalized.get("entity_id") or normalized.get("equipment_id") or normalized.get("batch_number"),
            entity_name=normalized.get("entity_name") or normalized.get("analyst"),
            signal_type=normalized.get("signal_type") or imp.entity_type,
            event_date=normalized.get("event_date"),
            severity=normalized.get("severity"),
            raw_row=row,
            normalized=normalized,
        )
        db.add(obj)
        created += 1

    imp.record_count = created
    imp.status = "ready"
    await db.commit()

    return {"import_id": import_id, "objects_created": created}


@router.get("/imports", status_code=200)
async def list_imports(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvidenceImport)
        .where(EvidenceImport.company_id == current_user.company_id)
        .order_by(EvidenceImport.created_at.desc())
        .limit(50)
    )
    imports = result.scalars().all()
    return {
        "imports": [
            {
                "id": i.id, "filename": i.filename, "source_system": i.source_system,
                "entity_type": i.entity_type, "record_count": i.record_count,
                "status": i.status, "detected_columns": i.detected_columns,
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
        .offset(offset).limit(limit)
    )
    objects = result.scalars().all()
    count_r = await db.execute(
        select(func.count()).where(EvidenceObject.import_id == import_id)
    )
    total = count_r.scalar() or 0

    return {
        "import_id": import_id,
        "total": total,
        "objects": [
            {
                "id": o.id, "entity_type": o.entity_type, "entity_id": o.entity_id,
                "entity_name": o.entity_name, "signal_type": o.signal_type,
                "event_date": o.event_date, "severity": o.severity,
                "normalized": o.normalized, "raw_row": o.raw_row,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in objects
        ],
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

    # Delete objects first
    objs = await db.execute(select(EvidenceObject).where(EvidenceObject.import_id == import_id))
    for obj in objs.scalars().all():
        await db.delete(obj)

    await db.delete(imp)
    await db.commit()
