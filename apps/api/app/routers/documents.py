"""
Document Management Router — Upload, Classification, AI Create, CRUD
"""
import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.document import Document, DocumentReference
from app.models.user import User
from app.services.document_service import DocumentService

router = APIRouter()

ALLOWED_TYPES = {"pdf", "docx", "doc", "xlsx", "xls"}


class DocumentOut(BaseModel):
    id: str
    title: str
    document_number: Optional[str] = None
    version: Optional[str] = None
    document_category: Optional[str] = None
    function_type: Optional[str] = None
    regulatory_category: Optional[str] = None
    department_owner: Optional[str] = None
    dtap_id: Optional[str] = None
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    status: str
    latest_score: Optional[float] = None
    latest_assessment_id: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/search", response_model=dict)
async def search_documents(
    q: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across document titles, numbers, and extracted text.
    Returns top matches with a short excerpt highlighting the match.
    """
    from sqlalchemy import or_, cast, String
    q_stripped = q.strip()
    if not q_stripped:
        return {"results": [], "query": q}

    pattern = f"%{q_stripped}%"
    result = await db.execute(
        select(Document)
        .where(
            Document.company_id == current_user.company_id,
            or_(
                Document.title.ilike(pattern),
                Document.document_number.ilike(pattern),
                Document.extracted_text.ilike(pattern),
            ),
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    documents = result.scalars().all()

    def _excerpt(text: str | None, query: str, window: int = 150) -> str:
        if not text:
            return ""
        idx = text.lower().find(query.lower())
        if idx == -1:
            return text[:window]
        start = max(0, idx - 60)
        end = min(len(text), idx + window - 60)
        snippet = text[start:end].replace("\n", " ").strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet = snippet + "…"
        return snippet

    rows = []
    for d in documents:
        in_title = q_stripped.lower() in (d.title or "").lower()
        in_number = q_stripped.lower() in (d.document_number or "").lower()
        rows.append({
            "id": d.id,
            "title": d.title,
            "document_number": d.document_number,
            "document_category": d.document_category,
            "department_owner": d.department_owner,
            "status": d.status,
            "latest_score": d.latest_score,
            "match_in": "title" if in_title else ("number" if in_number else "content"),
            "excerpt": _excerpt(d.extracted_text, q_stripped),
        })

    return {"results": rows, "query": q, "count": len(rows)}


@router.get("/", response_model=dict)
async def list_documents(
    document_category: Optional[str] = None,
    department_owner: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = [Document.company_id == current_user.company_id]
    if document_category:
        base_filter.append(Document.document_category == document_category)
    if department_owner:
        base_filter.append(Document.department_owner == department_owner)
    if status_filter:
        base_filter.append(Document.status == status_filter)

    count_result = await db.execute(select(func.count()).select_from(Document).where(*base_filter))
    total = count_result.scalar_one()

    query = select(Document).where(*base_filter).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Batch-fetch latest adjusted_score for each assessed document
    from app.models.assessment import Assessment
    from sqlalchemy import desc as sa_desc
    doc_ids = [d.id for d in documents]
    adjusted_map: dict[str, float | None] = {}
    if doc_ids:
        a_result = await db.execute(
            select(Assessment.document_id, Assessment.adjusted_score)
            .where(Assessment.document_id.in_(doc_ids), Assessment.status == "completed")
            .order_by(sa_desc(Assessment.created_at))
        )
        for doc_id, adj in a_result.all():
            if doc_id not in adjusted_map:
                adjusted_map[doc_id] = adj

    rows = []
    for d in documents:
        row = DocumentOut.model_validate(d).model_dump()
        adj = adjusted_map.get(d.id)
        row["adjusted_score"] = adj
        rows.append(row)

    return {
        "documents": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    department_owner: Optional[str] = Form(None),
    document_category: Optional[str] = Form(None),
    regulatory_frameworks: Optional[str] = Form(None),  # JSON array string
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_TYPES)}",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    import json as _json
    frameworks_list = None
    if regulatory_frameworks:
        try:
            frameworks_list = _json.loads(regulatory_frameworks)
        except Exception as e:
            logger.warning(f"Failed to parse regulatory_frameworks JSON: {e} — value: {regulatory_frameworks[:100]}")

    svc = DocumentService(db)
    document = await svc.upload_document(
        file_content=content,
        filename=safe_filename,
        company_id=current_user.company_id,
        user_id=current_user.id,
        metadata={
            "title": title or file.filename,
            "document_category": document_category or "",
            "department_owner": department_owner or "",
            "regulatory_frameworks": frameworks_list,
        },
    )
    return DocumentOut.model_validate(document)


@router.post("/create", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_type: str = Form(...),
    title: str = Form(...),
    department: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI Document Creator — creates a skeleton document and stores it.
    Full AI drafting requires an Anthropic API key.
    """
    placeholder_text = (
        f"# {title}\n\n"
        f"Document Type: {document_type}\n"
        f"Department: {department or 'Unassigned'}\n\n"
        f"## Purpose\n[To be completed]\n\n"
        f"## Scope\n[To be completed]\n\n"
        f"## Responsibilities\n[To be completed]\n\n"
        f"## Procedure\n[To be completed]\n\n"
        f"## References\n[To be completed]\n\n"
        f"## Revision History\n| Version | Date | Author | Description |\n|---|---|---|---|\n| 1.0 | - | - | Initial draft |"
    )
    content = placeholder_text.encode("utf-8")
    safe_filename = f"{uuid.uuid4().hex}_{title.replace(' ', '_')}.txt"

    svc = DocumentService(db)
    document = await svc.upload_document(
        file_content=content,
        filename=safe_filename,
        company_id=current_user.company_id,
        user_id=current_user.id,
        metadata={
            "title": title,
            "document_category": document_type,
            "department_owner": department or "",
        },
    )
    return DocumentOut.model_validate(document)


@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == current_user.company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    svc = DocumentService(db)
    data = await svc.get_document_with_references(document_id)
    doc_out = DocumentOut.model_validate(data["document"]).model_dump()
    doc_out["references"] = [
        {"id": r["id"], "title": r["title"], "reference_type": r["reference_type"]}
        for r in data["references"]
    ]
    return doc_out


@router.post("/{document_id}/references", status_code=status.HTTP_201_CREATED)
async def add_references(
    document_id: str,
    files: list[UploadFile] = File(...),
    reference_type: Optional[str] = Form("organizational_guideline"),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == current_user.company_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    svc = DocumentService(db)
    added = []
    for file in files:
        content = await file.read()
        ref = await svc.add_reference(
            document_id=document_id,
            file_content=content,
            filename=f"{uuid.uuid4().hex}_{file.filename}",
            user_id=current_user.id,
            title=file.filename,
            description=description or "",
            reference_type=reference_type,
        )
        added.append({"id": ref.id, "title": ref.title})

    return {"document_id": document_id, "references_added": len(added), "references": added}


@router.get("/{document_id}/assessment-history", response_model=dict)
async def get_assessment_history(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all completed assessments for a document, ordered newest first.
    Used for re-assessment version history comparison.
    """
    doc_result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == current_user.company_id,
        )
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    from app.models.assessment import Assessment
    from sqlalchemy import desc
    result = await db.execute(
        select(Assessment)
        .where(
            Assessment.document_id == document_id,
            Assessment.status == "completed",
        )
        .order_by(desc(Assessment.created_at))
    )
    assessments = result.scalars().all()

    return {
        "document_id": document_id,
        "assessments": [
            {
                "id": a.id,
                "clyira_score": a.clyira_score,
                "adjusted_score": a.adjusted_score,
                "score_band": a.score_band,
                "findings_critical": a.findings_critical,
                "findings_high": a.findings_high,
                "findings_medium": a.findings_medium,
                "findings_low": a.findings_low,
                "findings_info": a.findings_info,
                "data_integrity_hold": a.data_integrity_hold or False,
                "dtap_id": a.dtap_id,
                "levels_run": a.levels_run,
                "model_version": a.model_version,
                "processing_time_seconds": a.processing_time_seconds,
                "created_at": str(a.created_at),
            }
            for a in assessments
        ],
        "count": len(assessments),
    }
