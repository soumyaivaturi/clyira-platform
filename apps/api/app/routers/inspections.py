"""
Real-Time Audit Support Router — Module 3
Live inspection management, AI agents, request board, post-inspection
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.inspection import Inspection, InspectionRequest, InspectionLog
from app.models.user import User
from app.models.base import generate_uuid

router = APIRouter()


class InspectionCreate(BaseModel):
    title: str
    agency: Optional[str] = None
    inspection_type: Optional[str] = "routine"
    start_date: Optional[str] = None


class InspectionRequestCreate(BaseModel):
    request_text: str
    criticality: str = "medium"
    category: Optional[str] = "question"


class ScribeEntryCreate(BaseModel):
    content: str
    entry_type: str = "scribe_note"
    tags: list[str] = []


def _inspection_out(insp: Inspection) -> dict:
    return {
        "id": insp.id,
        "title": insp.title,
        "agency": insp.agency,
        "inspection_type": insp.inspection_type,
        "status": insp.status,
        "start_date": insp.start_date,
        "end_date": insp.end_date,
        "total_requests": insp.total_requests or 0,
        "created_at": str(insp.created_at),
    }


# ── Inspection lifecycle ────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
async def list_inspections(
    insp_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Inspection).where(Inspection.company_id == current_user.company_id)
    if insp_status:
        query = query.where(Inspection.status == insp_status)
    query = query.order_by(Inspection.created_at.desc())
    result = await db.execute(query)
    inspections = result.scalars().all()
    return {"inspections": [_inspection_out(i) for i in inspections], "total": len(inspections)}


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_inspection(
    data: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = Inspection(
        id=generate_uuid(),
        company_id=current_user.company_id,
        created_by=current_user.id,
        title=data.title,
        agency=data.agency,
        inspection_type=data.inspection_type,
        start_date=data.start_date,
        status="planned",
        ai_agents_active=["scribe", "prep_manager", "sme_coach", "qa_agent", "doc_reviewer"],
    )
    db.add(inspection)
    await db.flush()
    return _inspection_out(inspection)


@router.get("/{inspection_id}", response_model=dict)
async def get_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
        .order_by(InspectionRequest.created_at.desc())
    )
    requests = req_result.scalars().all()

    out = _inspection_out(inspection)
    out["requests"] = [
        {
            "id": r.id,
            "request_text": r.request_text,
            "criticality": r.criticality,
            "category": r.category,
            "status": r.status,
            "response_text": r.response_text,
            "created_at": str(r.created_at),
        }
        for r in requests
    ]
    out["ai_agents"] = inspection.ai_agents_active or []
    return out


@router.patch("/{inspection_id}/activate", response_model=dict)
async def activate_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    inspection.status = "active"
    return _inspection_out(inspection)


@router.post("/{inspection_id}/close", response_model=dict)
async def close_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    inspection.status = "post_inspection"
    return _inspection_out(inspection)


# ── Request board ───────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_request(
    inspection_id: str,
    data: InspectionRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    req = InspectionRequest(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_text=data.request_text,
        criticality=data.criticality,
        category=data.category or "question",
        status="open",
    )
    db.add(req)

    inspection.total_requests = (inspection.total_requests or 0) + 1
    await db.flush()

    return {
        "id": req.id,
        "inspection_id": inspection_id,
        "request_text": req.request_text,
        "criticality": req.criticality,
        "category": req.category,
        "status": req.status,
        "ai_suggested_documents": [],
        "ai_talking_points": [],
    }


@router.get("/{inspection_id}/requests", response_model=dict)
async def list_requests(
    inspection_id: str,
    req_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
    if req_status:
        query = query.where(InspectionRequest.status == req_status)
    query = query.order_by(InspectionRequest.created_at.desc())
    result = await db.execute(query)
    requests = result.scalars().all()

    return {
        "inspection_id": inspection_id,
        "requests": [
            {
                "id": r.id,
                "request_text": r.request_text,
                "criticality": r.criticality,
                "category": r.category,
                "status": r.status,
                "response_text": r.response_text,
                "created_at": str(r.created_at),
            }
            for r in requests
        ],
    }


@router.patch("/{inspection_id}/requests/{request_id}", response_model=dict)
async def update_request(
    inspection_id: str,
    request_id: str,
    req_status: Optional[str] = None,
    response_text: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionRequest).where(
            InspectionRequest.id == request_id,
            InspectionRequest.inspection_id == inspection_id,
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req_status:
        req.status = req_status
    if response_text:
        req.response_text = response_text

    return {"request_id": request_id, "status": req.status, "updated": True}


# ── Scribe ──────────────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/scribe", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_scribe_entry(
    inspection_id: str,
    data: ScribeEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection not found")

    entry = InspectionLog(
        id=generate_uuid(),
        inspection_id=inspection_id,
        user_id=current_user.id,
        entry_type=data.entry_type,
        content=data.content,
        tags=data.tags,
    )
    db.add(entry)
    await db.flush()

    return {
        "id": entry.id,
        "inspection_id": inspection_id,
        "entry_type": entry.entry_type,
        "content": entry.content,
        "tags": entry.tags,
        "created_at": str(entry.created_at),
    }


@router.get("/{inspection_id}/log", response_model=dict)
async def get_log(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionLog).where(InspectionLog.inspection_id == inspection_id)
        .order_by(InspectionLog.created_at.asc())
    )
    entries = result.scalars().all()
    return {
        "inspection_id": inspection_id,
        "entries": [
            {
                "id": e.id,
                "entry_type": e.entry_type,
                "content": e.content,
                "tags": e.tags or [],
                "created_at": str(e.created_at),
            }
            for e in entries
        ],
    }


# ── WebSocket ───────────────────────────────────────────────────────────────────

@router.websocket("/{inspection_id}/ws")
async def inspection_websocket(websocket: WebSocket, inspection_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "inspection_id": inspection_id})
    except WebSocketDisconnect:
        pass
