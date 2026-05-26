"""
Real-Time Audit Support Router — Module 3
Live inspection management, AI agents, request board, post-inspection
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.inspection import Inspection, InspectionRequest, InspectionLog, SLA_MINUTES
from app.models.inspection_commitment import InspectionCommitment
from app.models.inspection_observation import InspectionObservation
from app.models.inspection_delivery import InspectionDeliveryLog
from app.models.inspection_inspector import InspectionInspector
from app.models.inspection_request_document import InspectionRequestDocument
from app.models.inspection_request_comment import InspectionRequestComment
from app.models.user import User
from app.models.base import generate_uuid

router = APIRouter()


# ── Serialisers ─────────────────────────────────────────────────────────────────

def _inspection_out(insp: Inspection) -> dict:
    return {
        "id": insp.id,
        "title": insp.title,
        "agency": insp.agency,
        "inspection_type": insp.inspection_type,
        "status": insp.status,
        "current_phase": insp.current_phase,
        "start_date": insp.start_date,
        "end_date": insp.end_date,
        "inspection_scope": insp.inspection_scope or [],
        "agenda": insp.agenda or [],
        "total_requests": insp.total_requests or 0,
        "ai_agents_count": len(insp.ai_agents_active) if insp.ai_agents_active else 0,
        "created_at": str(insp.created_at),
    }


def _request_out(r: InspectionRequest) -> dict:
    return {
        "id": r.id,
        "request_number": r.request_number,
        "request_text": r.request_text,
        "criticality": r.criticality,
        "category": r.category,
        "inspector_name": r.inspector_name,
        "inspector_department": r.inspector_department,
        "location": r.location,
        "assigned_to": r.assigned_to,
        "assigned_to_name": r.assigned_to_name,
        "assigned_to_title": r.assigned_to_title,
        "sla_minutes": r.sla_minutes,
        "due_at": r.due_at,
        "status": r.status,
        "fulfillment_progress": r.fulfillment_progress or 0,
        "response_text": r.response_text,
        "ai_talking_points": r.ai_talking_points or [],
        "ai_suggested_documents": r.ai_suggested_documents or [],
        "ai_risk_assessment": r.ai_risk_assessment,
        "created_at": str(r.created_at),
    }


# ── Schemas ──────────────────────────────────────────────────────────────────────

class InspectionCreate(BaseModel):
    title: str
    agency: Optional[str] = None
    inspection_type: Optional[str] = "routine"
    start_date: Optional[str] = None
    inspection_scope: Optional[list[str]] = None


class InspectionRequestCreate(BaseModel):
    request_text: str
    criticality: str = "medium"
    category: Optional[str] = "question"
    inspector_name: Optional[str] = None
    inspector_department: Optional[str] = None
    location: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_to_title: Optional[str] = None


class ScribeEntryCreate(BaseModel):
    content: str
    entry_type: str = "scribe_note"
    tags: list[str] = []
    location: Optional[str] = None


class CommitmentCreate(BaseModel):
    commitment_text: str
    committed_by: Optional[str] = None
    committed_to: Optional[str] = None
    deadline_at: Optional[str] = None
    request_id: Optional[str] = None


class ObservationCreate(BaseModel):
    observation_text: str
    system_area: Optional[str] = None
    cfr_citations: list[str] = []
    response_deadline: Optional[str] = None
    legal_review_required: bool = False


class DeliveryCreate(BaseModel):
    document_titles: list[str]
    delivered_to: Optional[str] = None
    delivery_method: str = "portal"
    request_id: Optional[str] = None
    notes: Optional[str] = None


class InspectorCreate(BaseModel):
    name: str
    fda_district: Optional[str] = None
    role: str = "lead"
    focus_areas: list[str] = []
    email: Optional[str] = None
    notes: Optional[str] = None


class RequestDocumentCreate(BaseModel):
    filename: str
    file_size_bytes: Optional[int] = None
    file_path: Optional[str] = None


class RequestCommentCreate(BaseModel):
    content: str


# ── Helpers ──────────────────────────────────────────────────────────────────────

async def _verify_inspection(db: AsyncSession, inspection_id: str, company_id: str) -> Inspection:
    result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == company_id,
        )
    )
    insp = result.scalar_one_or_none()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return insp


def _compute_due_at(criticality: str) -> tuple[int, str]:
    sla = SLA_MINUTES.get(criticality, 60)
    due = datetime.utcnow() + timedelta(minutes=sla)
    return sla, due.strftime("%Y-%m-%dT%H:%M:%S")


# ── Inspection lifecycle ─────────────────────────────────────────────────────────

@router.get("", response_model=dict)
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


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
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
        inspection_scope=data.inspection_scope or [],
        status="planned",
        total_requests=0,
        ai_agents_active=["scribe", "prep_manager", "sme_coach", "qa_agent", "doc_reviewer"],
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return _inspection_out(inspection)


@router.get("/{inspection_id}", response_model=dict)
async def get_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)

    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
        .order_by(InspectionRequest.request_number.asc().nullslast(), InspectionRequest.created_at.desc())
    )
    requests = req_result.scalars().all()

    inspectors_result = await db.execute(
        select(InspectionInspector).where(InspectionInspector.inspection_id == inspection_id)
    )
    inspectors = inspectors_result.scalars().all()

    out = _inspection_out(inspection)
    out["requests"] = [_request_out(r) for r in requests]
    out["ai_agents"] = inspection.ai_agents_active or []
    out["inspectors"] = [
        {
            "id": i.id,
            "name": i.name,
            "fda_district": i.fda_district,
            "role": i.role,
            "focus_areas": i.focus_areas or [],
            "email": i.email,
            "notes": i.notes,
        }
        for i in inspectors
    ]
    return out


@router.patch("/{inspection_id}/activate", response_model=dict)
async def activate_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)
    inspection.status = "active"
    inspection.current_phase = "opening_meeting"
    await db.commit()
    return _inspection_out(inspection)


@router.post("/{inspection_id}/close", response_model=dict)
async def close_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)
    inspection.status = "post_inspection"
    await db.commit()
    return _inspection_out(inspection)


@router.patch("/{inspection_id}/phase", response_model=dict)
async def update_phase(
    inspection_id: str,
    phase: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid = {"opening_meeting", "facility_tour", "document_review", "systems_review", "closing_meeting"}
    if phase not in valid:
        raise HTTPException(status_code=400, detail=f"phase must be one of: {', '.join(sorted(valid))}")
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)
    inspection.current_phase = phase
    await db.commit()
    return {"inspection_id": inspection_id, "current_phase": phase}


# ── Request board ────────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_request(
    inspection_id: str,
    data: InspectionRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)

    # Auto-increment request number within this inspection
    count_result = await db.execute(
        select(func.count()).select_from(InspectionRequest)
        .where(InspectionRequest.inspection_id == inspection_id)
    )
    next_number = (count_result.scalar() or 0) + 1

    sla_minutes, due_at = _compute_due_at(data.criticality)

    req = InspectionRequest(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_number=next_number,
        request_text=data.request_text,
        criticality=data.criticality,
        category=data.category or "question",
        inspector_name=data.inspector_name,
        inspector_department=data.inspector_department,
        location=data.location,
        assigned_to_name=data.assigned_to_name,
        assigned_to_title=data.assigned_to_title,
        sla_minutes=sla_minutes,
        due_at=due_at,
        status="open",
        fulfillment_progress=0,
    )
    db.add(req)

    inspection.total_requests = (inspection.total_requests or 0) + 1
    await db.commit()
    await db.refresh(req)
    return _request_out(req)


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
    query = query.order_by(InspectionRequest.request_number.asc().nullslast())
    result = await db.execute(query)
    return {"inspection_id": inspection_id, "requests": [_request_out(r) for r in result.scalars().all()]}


@router.get("/{inspection_id}/overdue-requests", response_model=dict)
async def overdue_requests(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    result = await db.execute(
        select(InspectionRequest).where(
            InspectionRequest.inspection_id == inspection_id,
            InspectionRequest.status.in_(["open", "in_progress"]),
            InspectionRequest.due_at <= now_str,
            InspectionRequest.due_at.isnot(None),
        )
    )
    overdue = result.scalars().all()
    return {"inspection_id": inspection_id, "overdue": [_request_out(r) for r in overdue], "count": len(overdue)}


@router.patch("/{inspection_id}/requests/{request_id}", response_model=dict)
async def update_request(
    inspection_id: str,
    request_id: str,
    req_status: Optional[str] = None,
    response_text: Optional[str] = None,
    fulfillment_progress: Optional[int] = None,
    assigned_to_name: Optional[str] = None,
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
        raise HTTPException(status_code=404, detail="Request not found")

    if req_status:
        req.status = req_status
    if response_text is not None:
        req.response_text = response_text
    if fulfillment_progress is not None:
        req.fulfillment_progress = max(0, min(100, fulfillment_progress))
    if assigned_to_name is not None:
        req.assigned_to_name = assigned_to_name

    await db.commit()
    # Push real-time update to all war room clients
    await ws_broadcast(inspection_id, {
        "type": "request_update",
        "inspection_id": inspection_id,
        "request_id": request_id,
        "status": req.status,
        "fulfillment_progress": req.fulfillment_progress,
    })
    return _request_out(req)


# ── Request documents ────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests/{request_id}/documents", response_model=dict, status_code=201)
async def add_request_document(
    inspection_id: str,
    request_id: str,
    data: RequestDocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = InspectionRequestDocument(
        id=generate_uuid(),
        request_id=request_id,
        inspection_id=inspection_id,
        filename=data.filename,
        file_size_bytes=data.file_size_bytes,
        file_path=data.file_path,
        status="pending",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "file_size_bytes": doc.file_size_bytes,
            "status": doc.status, "created_at": str(doc.created_at)}


@router.get("/{inspection_id}/requests/{request_id}/documents", response_model=dict)
async def list_request_documents(
    inspection_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionRequestDocument).where(
            InspectionRequestDocument.request_id == request_id,
            InspectionRequestDocument.inspection_id == inspection_id,
        ).order_by(InspectionRequestDocument.created_at.asc())
    )
    docs = result.scalars().all()
    return {
        "request_id": request_id,
        "documents": [
            {"id": d.id, "filename": d.filename, "file_size_bytes": d.file_size_bytes,
             "status": d.status, "created_at": str(d.created_at)}
            for d in docs
        ],
    }


@router.patch("/{inspection_id}/requests/{request_id}/documents/{doc_id}", response_model=dict)
async def update_request_document(
    inspection_id: str,
    request_id: str,
    doc_id: str,
    doc_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionRequestDocument).where(
            InspectionRequestDocument.id == doc_id,
            InspectionRequestDocument.request_id == request_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.status = doc_status
    await db.commit()
    return {"id": doc_id, "status": doc.status}


# ── Request comments ──────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests/{request_id}/comments", response_model=dict, status_code=201)
async def add_comment(
    inspection_id: str,
    request_id: str,
    data: RequestCommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = InspectionRequestComment(
        id=generate_uuid(),
        request_id=request_id,
        inspection_id=inspection_id,
        author_id=current_user.id,
        author_name=current_user.full_name,
        content=data.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {"id": comment.id, "author_name": comment.author_name,
            "content": comment.content, "created_at": str(comment.created_at)}


@router.get("/{inspection_id}/requests/{request_id}/comments", response_model=dict)
async def list_comments(
    inspection_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionRequestComment).where(
            InspectionRequestComment.request_id == request_id,
        ).order_by(InspectionRequestComment.created_at.asc())
    )
    comments = result.scalars().all()
    return {
        "request_id": request_id,
        "comments": [
            {"id": c.id, "author_name": c.author_name, "content": c.content,
             "created_at": str(c.created_at)}
            for c in comments
        ],
    }


# ── Commitments ───────────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/commitments", response_model=dict, status_code=201)
async def create_commitment(
    inspection_id: str,
    data: CommitmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    commitment = InspectionCommitment(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_id=data.request_id,
        commitment_text=data.commitment_text,
        committed_by=data.committed_by,
        committed_to=data.committed_to,
        deadline_at=data.deadline_at,
        status="pending",
        created_by=current_user.id,
    )
    db.add(commitment)
    await db.commit()
    await db.refresh(commitment)
    return {
        "id": commitment.id,
        "commitment_text": commitment.commitment_text,
        "committed_by": commitment.committed_by,
        "committed_to": commitment.committed_to,
        "deadline_at": commitment.deadline_at,
        "status": commitment.status,
        "created_at": str(commitment.created_at),
    }


@router.get("/{inspection_id}/commitments", response_model=dict)
async def list_commitments(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionCommitment).where(InspectionCommitment.inspection_id == inspection_id)
        .order_by(InspectionCommitment.created_at.asc())
    )
    items = result.scalars().all()
    return {
        "inspection_id": inspection_id,
        "commitments": [
            {
                "id": c.id,
                "commitment_text": c.commitment_text,
                "committed_by": c.committed_by,
                "committed_to": c.committed_to,
                "deadline_at": c.deadline_at,
                "status": c.status,
                "delivered_at": c.delivered_at,
                "delivery_note": c.delivery_note,
                "request_id": c.request_id,
                "created_at": str(c.created_at),
            }
            for c in items
        ],
    }


@router.patch("/{inspection_id}/commitments/{commitment_id}", response_model=dict)
async def update_commitment(
    inspection_id: str,
    commitment_id: str,
    commit_status: Optional[str] = None,
    delivery_note: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionCommitment).where(
            InspectionCommitment.id == commitment_id,
            InspectionCommitment.inspection_id == inspection_id,
        )
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    if commit_status:
        c.status = commit_status
        if commit_status == "delivered" and not c.delivered_at:
            c.delivered_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    if delivery_note is not None:
        c.delivery_note = delivery_note
    await db.commit()
    return {"id": commitment_id, "status": c.status, "delivered_at": c.delivered_at}


# ── 483 Observations ──────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/observations", response_model=dict, status_code=201)
async def create_observation(
    inspection_id: str,
    data: ObservationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    count_result = await db.execute(
        select(func.count()).select_from(InspectionObservation)
        .where(InspectionObservation.inspection_id == inspection_id)
    )
    next_num = (count_result.scalar() or 0) + 1

    obs = InspectionObservation(
        id=generate_uuid(),
        inspection_id=inspection_id,
        observation_number=next_num,
        observation_text=data.observation_text,
        system_area=data.system_area,
        cfr_citations=data.cfr_citations,
        response_deadline=data.response_deadline,
        legal_review_required=data.legal_review_required,
        status="draft",
        created_by=current_user.id,
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return _obs_out(obs)


def _obs_out(obs: InspectionObservation) -> dict:
    return {
        "id": obs.id,
        "observation_number": obs.observation_number,
        "observation_text": obs.observation_text,
        "system_area": obs.system_area,
        "cfr_citations": obs.cfr_citations or [],
        "draft_response": obs.draft_response,
        "supporting_evidence": obs.supporting_evidence or [],
        "response_deadline": obs.response_deadline,
        "legal_review_required": obs.legal_review_required,
        "status": obs.status,
        "created_at": str(obs.created_at),
    }


@router.get("/{inspection_id}/observations", response_model=dict)
async def list_observations(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionObservation).where(InspectionObservation.inspection_id == inspection_id)
        .order_by(InspectionObservation.observation_number.asc())
    )
    return {"inspection_id": inspection_id, "observations": [_obs_out(o) for o in result.scalars().all()]}


@router.patch("/{inspection_id}/observations/{obs_id}", response_model=dict)
async def update_observation(
    inspection_id: str,
    obs_id: str,
    obs_status: Optional[str] = None,
    draft_response: Optional[str] = None,
    supporting_evidence: Optional[list[str]] = None,
    legal_review_required: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionObservation).where(
            InspectionObservation.id == obs_id,
            InspectionObservation.inspection_id == inspection_id,
        )
    )
    obs = result.scalar_one_or_none()
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    if obs_status:
        obs.status = obs_status
    if draft_response is not None:
        obs.draft_response = draft_response
    if supporting_evidence is not None:
        obs.supporting_evidence = supporting_evidence
    if legal_review_required is not None:
        obs.legal_review_required = legal_review_required
    await db.commit()
    return _obs_out(obs)


@router.post("/{inspection_id}/observations/{obs_id}/draft-response", response_model=dict)
async def ai_draft_observation_response(
    inspection_id: str,
    obs_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.engines.llm_engine import _llm_available, _call_llm
    from app.models.document import Document
    result = await db.execute(
        select(InspectionObservation).where(
            InspectionObservation.id == obs_id,
            InspectionObservation.inspection_id == inspection_id,
        )
    )
    obs = result.scalar_one_or_none()
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    if not _llm_available():
        return {"obs_id": obs_id, "draft_response": "LLM not configured.", "error": "llm_unavailable"}

    doc_result = await db.execute(
        select(Document.title).where(Document.company_id == current_user.company_id).limit(30)
    )
    doc_titles = "\n".join(f"- {r[0]}" for r in doc_result.all())

    prompt = f"""You are a regulatory expert drafting a formal FDA Form 483 observation response.

Observation #{obs.observation_number}: {obs.observation_text}
System area: {obs.system_area or "Not specified"}
CFR citations: {', '.join(obs.cfr_citations or []) or "Not specified"}

Available company documents:
{doc_titles or "No documents listed."}

Draft a professional, factual FDA 483 response that:
1. Acknowledges the observation without admitting systematic failure
2. Describes immediate corrective action already taken
3. Describes the long-term CAPA plan with a specific timeline
4. References any relevant SOPs or records
5. Ends with a commitment statement

Keep the tone factual and respectful. Use 3-5 paragraphs. Respond with the draft text only."""

    try:
        draft = await _call_llm(
            "You are a pharmaceutical regulatory affairs expert writing FDA 483 responses.",
            prompt,
        )
        obs.draft_response = draft
        await db.commit()
        return {"obs_id": obs_id, "draft_response": draft}
    except Exception as e:
        logger.warning(f"483 draft failed: {e}")
        return {"obs_id": obs_id, "draft_response": None, "error": str(e)}


# ── Document delivery log ──────────────────────────────────────────────────────────

@router.post("/{inspection_id}/deliveries", response_model=dict, status_code=201)
async def log_delivery(
    inspection_id: str,
    data: DeliveryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    entry = InspectionDeliveryLog(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_id=data.request_id,
        document_titles=data.document_titles,
        delivered_to=data.delivered_to,
        delivery_method=data.delivery_method,
        delivered_by=current_user.id,
        delivered_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        notes=data.notes,
    )
    db.add(entry)

    # Mark linked request as fulfilled if provided
    if data.request_id:
        req_result = await db.execute(
            select(InspectionRequest).where(InspectionRequest.id == data.request_id)
        )
        req = req_result.scalar_one_or_none()
        if req and req.status not in ("fulfilled", "declined"):
            req.status = "fulfilled"
            req.fulfillment_progress = 100

    await db.commit()
    await db.refresh(entry)
    return {
        "id": entry.id,
        "document_titles": entry.document_titles,
        "delivered_to": entry.delivered_to,
        "delivery_method": entry.delivery_method,
        "delivered_at": entry.delivered_at,
        "acknowledgment_received": entry.acknowledgment_received,
        "notes": entry.notes,
        "created_at": str(entry.created_at),
    }


@router.get("/{inspection_id}/deliveries", response_model=dict)
async def list_deliveries(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionDeliveryLog).where(InspectionDeliveryLog.inspection_id == inspection_id)
        .order_by(InspectionDeliveryLog.created_at.desc())
    )
    items = result.scalars().all()
    return {
        "inspection_id": inspection_id,
        "deliveries": [
            {
                "id": d.id,
                "document_titles": d.document_titles or [],
                "delivered_to": d.delivered_to,
                "delivery_method": d.delivery_method,
                "delivered_at": d.delivered_at,
                "acknowledgment_received": d.acknowledgment_received,
                "request_id": d.request_id,
                "notes": d.notes,
                "created_at": str(d.created_at),
            }
            for d in items
        ],
        "total_docs": sum(len(d.document_titles or []) for d in items),
    }


# ── Inspector profiles ──────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/inspectors", response_model=dict, status_code=201)
async def add_inspector(
    inspection_id: str,
    data: InspectorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    inspector = InspectionInspector(
        id=generate_uuid(),
        inspection_id=inspection_id,
        name=data.name,
        fda_district=data.fda_district,
        role=data.role,
        focus_areas=data.focus_areas,
        email=data.email,
        notes=data.notes,
    )
    db.add(inspector)
    await db.commit()
    await db.refresh(inspector)
    return {
        "id": inspector.id,
        "name": inspector.name,
        "fda_district": inspector.fda_district,
        "role": inspector.role,
        "focus_areas": inspector.focus_areas or [],
        "email": inspector.email,
        "notes": inspector.notes,
    }


@router.get("/{inspection_id}/inspectors", response_model=dict)
async def list_inspectors(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionInspector).where(InspectionInspector.inspection_id == inspection_id)
    )
    items = result.scalars().all()
    return {
        "inspection_id": inspection_id,
        "inspectors": [
            {"id": i.id, "name": i.name, "fda_district": i.fda_district, "role": i.role,
             "focus_areas": i.focus_areas or [], "email": i.email, "notes": i.notes}
            for i in items
        ],
    }


@router.delete("/{inspection_id}/inspectors/{inspector_id}", status_code=204)
async def remove_inspector(
    inspection_id: str,
    inspector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InspectionInspector).where(
            InspectionInspector.id == inspector_id,
            InspectionInspector.inspection_id == inspection_id,
        )
    )
    inspector = result.scalar_one_or_none()
    if not inspector:
        raise HTTPException(status_code=404, detail="Inspector not found")
    await db.delete(inspector)
    await db.commit()


# ── AI Inspector Briefing ─────────────────────────────────────────────────────────

@router.post("/{inspection_id}/inspectors/{inspector_id}/brief", response_model=dict)
async def generate_inspector_brief(
    inspection_id: str,
    inspector_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI briefing on the inspector — district patterns, known focus areas, prep guidance."""
    from app.engines.llm_engine import _llm_available, _call_llm
    import json, re

    await _verify_inspection(db, inspection_id, current_user.company_id)

    result = await db.execute(
        select(InspectionInspector).where(
            InspectionInspector.id == inspector_id,
            InspectionInspector.inspection_id == inspection_id,
        )
    )
    inspector = result.scalar_one_or_none()
    if not inspector:
        raise HTTPException(status_code=404, detail="Inspector not found")

    insp_result = await db.execute(
        select(Inspection).where(Inspection.id == inspection_id)
    )
    inspection = insp_result.scalar_one_or_none()

    if not _llm_available():
        return {
            "inspector_id": inspector_id,
            "brief": None,
            "error": "llm_unavailable",
            "message": "Configure an LLM API key to enable AI briefings.",
        }

    focus_str = ", ".join(inspector.focus_areas) if inspector.focus_areas else "not specified"
    agency = inspection.agency if inspection else "FDA"

    prompt = f"""You are a regulatory intelligence expert briefing a pharmaceutical quality team before an FDA inspection.

Inspector details:
- Name: {inspector.name}
- Agency/District: {inspector.fda_district or agency}
- Role: {inspector.role}
- Known focus areas: {focus_str}
- Notes: {inspector.notes or "none"}

Inspection type: {inspection.inspection_type if inspection else "routine"} — Agency: {agency}

Generate a pre-inspection intelligence brief. Respond with ONLY valid JSON:
{{
  "district_profile": "<2-3 sentences on the FDA district office known inspection approach and priorities>",
  "inspector_style": "<1-2 sentences on likely inspection style based on role and focus areas>",
  "likely_focus_areas": [
    "<specific system or topic area 1>",
    "<specific system or topic area 2>",
    "<specific system or topic area 3>",
    "<specific system or topic area 4>"
  ],
  "common_citations": [
    {{"cfr": "<e.g. 21 CFR 211.68>", "topic": "<brief description>"}},
    {{"cfr": "<citation>", "topic": "<description>"}},
    {{"cfr": "<citation>", "topic": "<description>"}}
  ],
  "opening_meeting_tips": [
    "<actionable tip for opening meeting 1>",
    "<actionable tip 2>",
    "<actionable tip 3>"
  ],
  "red_flags": [
    "<document type or system area to have fully prepared>",
    "<potential risk area to review before inspection starts>"
  ],
  "overall_assessment": "<1-2 sentence overall risk level and recommended posture for this inspector>"
}}"""

    try:
        raw = await _call_llm(
            "You are a pharmaceutical regulatory intelligence expert.",
            prompt,
        )
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            raise ValueError("No JSON in LLM response")
        brief_data = json.loads(json_match.group())
        return {
            "inspector_id": inspector_id,
            "inspector_name": inspector.name,
            "brief": brief_data,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        logger.warning(f"Inspector brief generation failed: {e}")
        return {
            "inspector_id": inspector_id,
            "brief": None,
            "error": str(e),
            "message": "Brief generation failed. Please retry.",
        }


# ── Cross-request risk analysis ────────────────────────────────────────────────────

@router.post("/{inspection_id}/risk-analysis", response_model=dict)
async def run_risk_analysis(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.engines.llm_engine import _llm_available, _call_llm
    import json, re

    await _verify_inspection(db, inspection_id, current_user.company_id)

    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
        .order_by(InspectionRequest.created_at.asc())
    )
    requests = req_result.scalars().all()

    if not requests:
        return {"inspection_id": inspection_id, "risk_areas": [], "overall_risk": "No requests yet.",
                "recommendation": "Begin logging inspector requests to enable risk analysis."}

    if not _llm_available():
        return {"inspection_id": inspection_id, "risk_areas": [], "overall_risk": "LLM unavailable.",
                "recommendation": "Configure LLM API key to enable risk analysis."}

    request_list = "\n".join(
        f"REQ-{r.request_number or '?'} [{r.criticality}] ({r.category}): {r.request_text}"
        for r in requests
    )

    prompt = f"""You are an FDA inspection expert analyzing patterns in inspector requests to predict likely 483 observations.

Inspector requests so far:
{request_list}

Analyze these requests and identify likely FDA 483 observation areas. Group related requests by regulatory topic.

Respond with ONLY valid JSON:
{{
  "risk_areas": [
    {{
      "area": "<system/topic area>",
      "cfr_section": "<primary CFR citation e.g. 21 CFR 211.188>",
      "request_count": <number of related requests>,
      "risk_level": "<high|medium|low>",
      "likelihood": "<percentage e.g. 78%>",
      "basis": "<1-2 sentence explanation of why this is a risk based on the request pattern>"
    }}
  ],
  "overall_risk": "<one sentence overall risk assessment>",
  "recommendation": "<one sentence top recommendation for the war room team>"
}}

Rank risk_areas from highest to lowest risk. Include all identifiable risk areas."""

    try:
        raw = await _call_llm(
            "You are an FDA inspection expert analyzing inspection request patterns.",
            prompt,
        )
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            raise ValueError("No JSON in response")
        data = json.loads(json_match.group())
        return {
            "inspection_id": inspection_id,
            "risk_areas": data.get("risk_areas", []),
            "overall_risk": data.get("overall_risk", ""),
            "recommendation": data.get("recommendation", ""),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "request_count": len(requests),
        }
    except Exception as e:
        logger.warning(f"Risk analysis failed: {e}")
        return {"inspection_id": inspection_id, "risk_areas": [], "overall_risk": "Analysis failed.",
                "recommendation": "Please retry.", "error": str(e)}


# ── Closing meeting summary ────────────────────────────────────────────────────────

@router.post("/{inspection_id}/closing-summary", response_model=dict)
async def generate_closing_summary(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.engines.llm_engine import _llm_available, _call_llm

    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)

    if not _llm_available():
        return {"inspection_id": inspection_id, "summary": "LLM not configured.", "error": "llm_unavailable"}

    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
    )
    requests = req_result.scalars().all()

    commit_result = await db.execute(
        select(InspectionCommitment).where(InspectionCommitment.inspection_id == inspection_id)
    )
    commitments = commit_result.scalars().all()

    obs_result = await db.execute(
        select(InspectionObservation).where(InspectionObservation.inspection_id == inspection_id)
    )
    observations = obs_result.scalars().all()

    requests_summary = "\n".join(
        f"- REQ-{r.request_number or '?'} [{r.status}]: {r.request_text[:120]}"
        for r in requests
    ) or "No requests logged."

    commitments_summary = "\n".join(
        f"- {c.commitment_text} (deadline: {c.deadline_at or 'TBD'}, status: {c.status})"
        for c in commitments
    ) or "No commitments logged."

    observations_summary = "\n".join(
        f"- OBS-{o.observation_number}: {o.observation_text[:120]} [{o.status}]"
        for o in observations
    ) or "No formal observations noted."

    prompt = f"""Generate a professional FDA inspection closing meeting summary.

Inspection: {inspection.title}
Agency: {inspection.agency or 'FDA'}
Type: {inspection.inspection_type or 'Routine GMP'}

REQUESTS RECEIVED ({len(requests)} total):
{requests_summary}

COMMITMENTS MADE ({len(commitments)} total):
{commitments_summary}

OBSERVATIONS NOTED ({len(observations)} total):
{observations_summary}

Write a structured closing meeting summary with these sections:
1. Inspection Overview (2-3 sentences on what was inspected)
2. Areas Reviewed (bullet list)
3. Outstanding Items (any open requests still pending)
4. Commitments Made (all commitments with deadlines)
5. Formal Observations (if any, with status)
6. Next Steps (what happens after the inspection closes)

Be professional, factual, and concise. This will be read in the closing meeting with the inspector present."""

    try:
        summary = await _call_llm(
            "You are a pharmaceutical GMP expert preparing an inspection closing meeting summary.",
            prompt,
        )
        return {
            "inspection_id": inspection_id,
            "summary": summary,
            "stats": {
                "total_requests": len(requests),
                "open_requests": sum(1 for r in requests if r.status in ("open", "in_progress")),
                "fulfilled_requests": sum(1 for r in requests if r.status == "fulfilled"),
                "total_commitments": len(commitments),
                "pending_commitments": sum(1 for c in commitments if c.status == "pending"),
                "total_observations": len(observations),
            },
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        logger.warning(f"Closing summary failed: {e}")
        return {"inspection_id": inspection_id, "summary": None, "error": str(e)}


@router.post("/{inspection_id}/cover-letter", response_model=dict)
async def generate_cover_letter(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.engines.llm_engine import _llm_available, _call_llm

    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)

    if not _llm_available():
        return {"inspection_id": inspection_id, "letter": None, "error": "llm_unavailable"}

    obs_result = await db.execute(
        select(InspectionObservation).where(InspectionObservation.inspection_id == inspection_id)
    )
    observations = obs_result.scalars().all()

    commit_result = await db.execute(
        select(InspectionCommitment).where(InspectionCommitment.inspection_id == inspection_id)
    )
    commitments = commit_result.scalars().all()

    obs_blocks = "\n\n".join(
        f"Observation {o.observation_number}: {o.observation_text}\n"
        f"System Area: {o.system_area or 'General'}\n"
        f"CFR Citations: {', '.join(o.cfr_citations or []) or 'Not specified'}\n"
        f"Draft Response: {o.draft_response or 'Not yet drafted'}"
        for o in observations
    ) or "No formal 483 observations were issued."

    commit_blocks = "\n".join(
        f"- {c.commitment_text} (deadline: {c.deadline_at or 'TBD'})"
        for c in commitments
    ) or "No commitments made during inspection."

    prompt = f"""Draft a formal FDA 483 Response Letter for the following inspection.

Company: {inspection.company_id}
Inspection Title: {inspection.title}
Agency: {inspection.agency or 'FDA'}
Inspection Type: {inspection.inspection_type or 'Routine GMP'}

FORM 483 OBSERVATIONS:
{obs_blocks}

COMMITMENTS MADE DURING INSPECTION:
{commit_blocks}

Draft a professional, regulatory-compliant cover letter that:
1. Opens with formal address to the FDA District Director
2. States commitment to quality and regulatory compliance
3. For each observation: acknowledges the finding, provides root cause analysis framework, describes corrective action plan, and states implementation timeline
4. Closes with a statement of management commitment
5. Uses 21 CFR Part 820 / 21 CFR Part 211 language as appropriate

Format as a proper business letter. Use [COMPANY NAME], [SITE ADDRESS], [QA DIRECTOR NAME], [DATE] as placeholders where specific data is needed."""

    try:
        letter = await _call_llm(
            "You are a regulatory affairs expert drafting a formal FDA 483 response letter on behalf of a pharmaceutical company.",
            prompt,
        )
        return {
            "inspection_id": inspection_id,
            "letter": letter,
            "observation_count": len(observations),
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        logger.warning(f"Cover letter generation failed: {e}")
        return {"inspection_id": inspection_id, "letter": None, "error": str(e)}


@router.post("/{inspection_id}/finalize", response_model=dict)
async def finalize_inspection(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inspection = await _verify_inspection(db, inspection_id, current_user.company_id)
    if inspection.status not in ("post_inspection", "active"):
        raise HTTPException(status_code=400, detail="Only post-inspection inspections can be finalized")
    inspection.status = "closed"
    await db.commit()
    return _inspection_out(inspection)


# ── Scribe ───────────────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/scribe", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_scribe_entry(
    inspection_id: str,
    data: ScribeEntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    entry = InspectionLog(
        id=generate_uuid(),
        inspection_id=inspection_id,
        user_id=current_user.id,
        entry_type=data.entry_type,
        content=data.content,
        tags=data.tags,
        location=data.location,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return {
        "id": entry.id,
        "inspection_id": inspection_id,
        "entry_type": entry.entry_type,
        "content": entry.content,
        "tags": entry.tags,
        "location": entry.location,
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
                "location": e.location,
                "created_at": str(e.created_at),
            }
            for e in entries
        ],
    }


# ── AI analysis (per-request) ──────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests/{request_id}/analyze", response_model=dict)
async def analyze_request(
    inspection_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.document import Document
    from app.engines.llm_engine import _llm_available
    import json, re

    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.id == request_id)
    )
    req = req_result.scalar_one_or_none()
    if not req or req.inspection_id != inspection_id:
        raise HTTPException(status_code=404, detail="Request not found")

    await _verify_inspection(db, inspection_id, current_user.company_id)

    doc_result = await db.execute(
        select(Document.title, Document.document_category, Document.department_owner, Document.latest_score)
        .where(Document.company_id == current_user.company_id)
        .order_by(Document.latest_score.desc().nullslast())
        .limit(40)
    )
    docs = doc_result.all()
    doc_list = "\n".join(
        f"- [{d.document_category or 'DOC'}] {d.title} ({d.department_owner or 'N/A'})"
        + (f" — Score: {d.latest_score:.0f}" if d.latest_score else "")
        for d in docs
    )

    if not _llm_available():
        return {
            "request_id": request_id,
            "ai_talking_points": ["LLM not configured — manual response required."],
            "ai_suggested_documents": [],
            "ai_risk_assessment": "LLM unavailable.",
        }

    prompt = f"""An FDA inspector has submitted the following request/question:
"{req.request_text}"

Criticality: {req.criticality} | Category: {req.category}
Inspector: {req.inspector_name or 'Unknown'} | Location: {req.location or 'Not specified'}

Available company documents:
{doc_list or "No documents found."}

Respond with a structured JSON object:
{{
  "talking_points": ["<3-5 concise bullet points of what to say to the inspector>"],
  "suggested_documents": ["<2-3 document titles from the list above>"],
  "risk_assessment": "<1-2 sentence regulatory risk assessment>"
}}

Be specific. Reference 21 CFR Part 211 or applicable regulations where relevant. JSON only."""

    try:
        from app.engines.llm_engine import _call_llm
        raw = await _call_llm(
            "You are a pharmaceutical regulatory expert supporting a GMP inspection war room.",
            prompt,
        )
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError("No JSON in response")

        talking_points = data.get("talking_points", [])
        suggested_docs = data.get("suggested_documents", [])
        risk_assessment = data.get("risk_assessment", "")

        req.ai_talking_points = talking_points
        req.ai_suggested_documents = suggested_docs
        req.ai_risk_assessment = risk_assessment
        await db.commit()

        return {
            "request_id": request_id,
            "ai_talking_points": talking_points,
            "ai_suggested_documents": suggested_docs,
            "ai_risk_assessment": risk_assessment,
        }
    except Exception as e:
        logger.warning(f"Request analysis failed: {e}")
        return {
            "request_id": request_id,
            "ai_talking_points": ["Analysis failed — please retry or respond manually."],
            "ai_suggested_documents": [],
            "ai_risk_assessment": "Analysis unavailable.",
            "error": str(e),
        }


# ── WebSocket connection manager ─────────────────────────────────────────────────

class _InspectionRoom:
    """Per-inspection broadcast room. Thread-safe via asyncio single-thread guarantee."""
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections = [c for c in self._connections if c is not ws]

    async def broadcast(self, message: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


_rooms: dict[str, _InspectionRoom] = defaultdict(_InspectionRoom)


async def ws_broadcast(inspection_id: str, message: dict):
    """Call from any endpoint to push an event to all connected war room clients."""
    if inspection_id in _rooms:
        await _rooms[inspection_id].broadcast(message)


@router.websocket("/{inspection_id}/ws")
async def inspection_websocket(websocket: WebSocket, inspection_id: str):
    room = _rooms[inspection_id]
    await room.connect(websocket)
    try:
        # Send initial presence count
        await websocket.send_json({
            "type": "presence",
            "inspection_id": inspection_id,
            "connected": room.count,
        })
        # Broadcast join event to others
        await room.broadcast({
            "type": "presence",
            "inspection_id": inspection_id,
            "connected": room.count,
        })
        while True:
            raw = await websocket.receive_text()
            try:
                import json
                msg = json.loads(raw)
                event_type = msg.get("type", "ping")
                if event_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif event_type == "scribe_note":
                    # Broadcast real-time scribe note to all room members
                    await room.broadcast({
                        "type": "scribe_note",
                        "inspection_id": inspection_id,
                        "content": msg.get("content", ""),
                        "entry_type": msg.get("entry_type", "scribe_note"),
                        "author": msg.get("author", "Team"),
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                    })
                elif event_type == "request_update":
                    await room.broadcast({
                        "type": "request_update",
                        "inspection_id": inspection_id,
                        "request_id": msg.get("request_id"),
                        "status": msg.get("status"),
                        "fulfillment_progress": msg.get("fulfillment_progress"),
                    })
                elif event_type == "sla_alert":
                    await room.broadcast({
                        "type": "sla_alert",
                        "inspection_id": inspection_id,
                        "request_id": msg.get("request_id"),
                        "request_text": msg.get("request_text", ""),
                        "criticality": msg.get("criticality", "medium"),
                    })
            except Exception:
                pass
    except WebSocketDisconnect:
        room.disconnect(websocket)
        await room.broadcast({
            "type": "presence",
            "inspection_id": inspection_id,
            "connected": room.count,
        })
