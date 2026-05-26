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
from app.models.inspection_message import InspectionMessage
from app.models.inspection_potential_finding import InspectionPotentialFinding
from app.models.inspection_evidence_package import InspectionEvidencePackage
from app.models.inspection_sme import InspectionSME
from app.models.inspection_capa import InspectionCAPA
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
        "request_type": r.request_type,
        "request_category": r.request_category,
        "regulatory_risk": r.regulatory_risk or "low",
        "related_lot": r.related_lot,
        "related_product": r.related_product,
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
        "qa_reviewed_at": r.qa_reviewed_at,
        "qa_notes": r.qa_notes,
        "released_at": r.released_at,
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
    request_type: Optional[str] = None
    request_category: Optional[str] = None
    regulatory_risk: str = "low"
    related_lot: Optional[str] = None
    related_product: Optional[str] = None
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
        request_type=data.request_type,
        request_category=data.request_category,
        regulatory_risk=data.regulatory_risk,
        related_lot=data.related_lot,
        related_product=data.related_product,
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


# ── Potential Findings ───────────────────────────────────────────────────────────

class PotentialFindingCreate(BaseModel):
    title: str
    inspector_framing: Optional[str] = None
    system_area: Optional[str] = None
    cfr_citations: list[str] = []
    confidence: str = "medium"
    defense_summary: Optional[str] = None
    linked_request_ids: list[str] = []
    linked_document_ids: list[str] = []


class PotentialFindingUpdate(BaseModel):
    title: Optional[str] = None
    inspector_framing: Optional[str] = None
    system_area: Optional[str] = None
    cfr_citations: Optional[list[str]] = None
    confidence: Optional[str] = None
    status: Optional[str] = None
    defense_summary: Optional[str] = None
    linked_request_ids: Optional[list[str]] = None
    linked_document_ids: Optional[list[str]] = None


def _pf_out(pf: InspectionPotentialFinding) -> dict:
    return {
        "id": pf.id,
        "inspection_id": pf.inspection_id,
        "title": pf.title,
        "inspector_framing": pf.inspector_framing,
        "system_area": pf.system_area,
        "cfr_citations": pf.cfr_citations or [],
        "confidence": pf.confidence,
        "status": pf.status,
        "defense_summary": pf.defense_summary,
        "linked_request_ids": pf.linked_request_ids or [],
        "linked_document_ids": pf.linked_document_ids or [],
        "qa_reviewed": pf.qa_reviewed,
        "qa_reviewed_by": pf.qa_reviewed_by,
        "qa_reviewed_at": pf.qa_reviewed_at,
        "ai_generated": pf.ai_generated,
        "source": pf.source,
        "created_at": str(pf.created_at),
    }


@router.post("/{inspection_id}/potential-findings", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_potential_finding(
    inspection_id: str,
    data: PotentialFindingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    pf = InspectionPotentialFinding(
        id=generate_uuid(),
        inspection_id=inspection_id,
        created_by=current_user.id,
        title=data.title,
        inspector_framing=data.inspector_framing,
        system_area=data.system_area,
        cfr_citations=data.cfr_citations,
        confidence=data.confidence,
        defense_summary=data.defense_summary,
        linked_request_ids=data.linked_request_ids,
        linked_document_ids=data.linked_document_ids,
        source="manual",
    )
    db.add(pf)
    await db.commit()
    await db.refresh(pf)

    out = _pf_out(pf)
    await ws_broadcast(inspection_id, {"type": "potential_finding_added", **out})
    return out


@router.get("/{inspection_id}/potential-findings", response_model=dict)
async def list_potential_findings(
    inspection_id: str,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    filters = [InspectionPotentialFinding.inspection_id == inspection_id]
    if status_filter:
        filters.append(InspectionPotentialFinding.status == status_filter)

    result = await db.execute(
        select(InspectionPotentialFinding)
        .where(*filters)
        .order_by(InspectionPotentialFinding.created_at.desc())
    )
    findings = result.scalars().all()
    return {"inspection_id": inspection_id, "findings": [_pf_out(f) for f in findings]}


@router.patch("/{inspection_id}/potential-findings/{finding_id}", response_model=dict)
async def update_potential_finding(
    inspection_id: str,
    finding_id: str,
    data: PotentialFindingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    result = await db.execute(
        select(InspectionPotentialFinding).where(
            InspectionPotentialFinding.id == finding_id,
            InspectionPotentialFinding.inspection_id == inspection_id,
        )
    )
    pf = result.scalar_one_or_none()
    if not pf:
        raise HTTPException(status_code=404, detail="Potential finding not found")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(pf, field, val)

    await db.commit()
    await db.refresh(pf)

    out = _pf_out(pf)
    await ws_broadcast(inspection_id, {"type": "potential_finding_updated", **out})
    return out


@router.post("/{inspection_id}/potential-findings/{finding_id}/qa-review", response_model=dict)
async def qa_review_finding(
    inspection_id: str,
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    result = await db.execute(
        select(InspectionPotentialFinding).where(
            InspectionPotentialFinding.id == finding_id,
            InspectionPotentialFinding.inspection_id == inspection_id,
        )
    )
    pf = result.scalar_one_or_none()
    if not pf:
        raise HTTPException(status_code=404, detail="Potential finding not found")

    pf.qa_reviewed = not pf.qa_reviewed
    pf.qa_reviewed_by = current_user.id if pf.qa_reviewed else None
    pf.qa_reviewed_at = datetime.utcnow().isoformat() if pf.qa_reviewed else None
    await db.commit()
    await db.refresh(pf)
    return _pf_out(pf)


@router.delete("/{inspection_id}/potential-findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_potential_finding(
    inspection_id: str,
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionPotentialFinding).where(
            InspectionPotentialFinding.id == finding_id,
            InspectionPotentialFinding.inspection_id == inspection_id,
        )
    )
    pf = result.scalar_one_or_none()
    if pf:
        await db.delete(pf)
        await db.commit()


@router.post("/{inspection_id}/potential-findings/ai-scan", response_model=dict)
async def ai_scan_for_findings(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI scans all open requests + scribe notes for the inspection and identifies
    patterns that suggest the inspector is building toward a 483 observation.
    Returns a list of potential findings to review and accept/dismiss.
    """
    from app.engines.llm_engine import _call_llm, _llm_available
    import json, re

    insp = await _verify_inspection(db, inspection_id, current_user.company_id)

    # Gather context: open requests and recent scribe notes
    req_result = await db.execute(
        select(InspectionRequest)
        .where(InspectionRequest.inspection_id == inspection_id)
        .order_by(InspectionRequest.created_at.asc())
        .limit(50)
    )
    requests = req_result.scalars().all()

    log_result = await db.execute(
        select(InspectionLog)
        .where(InspectionLog.inspection_id == inspection_id)
        .order_by(InspectionLog.created_at.desc())
        .limit(30)
    )
    log_entries = log_result.scalars().all()

    if not requests and not log_entries:
        return {"findings": [], "message": "No requests or scribe notes to analyze yet."}

    req_context = "\n".join(
        f"REQ-{r.request_number or '?'} [{r.criticality}] {r.request_text}"
        for r in requests
    )
    log_context = "\n".join(
        f"[{e.entry_type}] {e.content}"
        for e in log_entries
    ) if log_entries else "No scribe notes yet."

    prompt = f"""You are an experienced FDA inspection host with 20 years of regulatory experience.

Analyze the following inspection data and identify potential 483 observations the inspector may be building toward.

INSPECTION: {insp.title}
AGENCY: {insp.agency or "FDA"}

INSPECTOR REQUESTS:
{req_context}

SCRIBE NOTES:
{log_context}

Based on patterns in these requests and observations, identify up to 5 potential 483 findings the inspector appears to be building toward.

For each potential finding, respond with valid JSON array:
[
  {{
    "title": "Short descriptive title (max 60 chars)",
    "inspector_framing": "How inspector would write this in a 483 observation (1-2 sentences, formal regulatory language)",
    "system_area": "Regulatory system area (e.g. Batch Records, Sterility Assurance, Equipment Qualification)",
    "cfr_citations": ["21 CFR 211.XX", ...],
    "confidence": "low|medium|high|certain",
    "defense_summary": "Key defense points and documents that rebut this finding",
    "linked_request_numbers": [1, 3, 5]
  }}
]

Only return the JSON array. If no patterns suggest a 483, return [].
"""

    if not _llm_available():
        return {"findings": [], "message": "LLM not available. Configure GROQ_API_KEY or GEMINI_API_KEY."}

    raw = await _call_llm(prompt, max_tokens=2000)

    # Parse JSON from response
    try:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match:
            return {"findings": [], "message": "AI did not return parseable findings."}
        items = json.loads(match.group())
    except Exception:
        return {"findings": [], "message": "AI response could not be parsed."}

    # Build request number → id map
    req_num_map = {r.request_number: r.id for r in requests if r.request_number}

    # Persist findings and return
    created = []
    for item in items[:5]:
        linked_ids = [req_num_map[n] for n in item.get("linked_request_numbers", []) if n in req_num_map]
        pf = InspectionPotentialFinding(
            id=generate_uuid(),
            inspection_id=inspection_id,
            created_by=current_user.id,
            title=item.get("title", "Untitled Finding"),
            inspector_framing=item.get("inspector_framing"),
            system_area=item.get("system_area"),
            cfr_citations=item.get("cfr_citations", []),
            confidence=item.get("confidence", "medium"),
            defense_summary=item.get("defense_summary"),
            linked_request_ids=linked_ids,
            ai_generated=True,
            source="ai_scan",
        )
        db.add(pf)
        created.append(pf)

    await db.commit()
    for pf in created:
        await db.refresh(pf)

    out = [_pf_out(pf) for pf in created]
    await ws_broadcast(inspection_id, {"type": "ai_scan_complete", "inspection_id": inspection_id, "count": len(out)})
    return {"findings": out, "count": len(out)}


# ── Inspection Setup (Section 1 extended) ────────────────────────────────────────

class InspectionSetupUpdate(BaseModel):
    title: Optional[str] = None
    agency: Optional[str] = None
    inspection_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sector: Optional[str] = None
    products_in_scope: Optional[list[str]] = None
    departments_in_scope: Optional[list[str]] = None
    regulatory_frameworks: Optional[list[str]] = None
    site_name: Optional[str] = None
    mode: Optional[str] = None
    inspection_scope: Optional[list[str]] = None
    team_assignments: Optional[dict] = None
    default_sla_settings: Optional[dict] = None


@router.patch("/{inspection_id}/setup", response_model=dict)
async def update_inspection_setup(
    inspection_id: str,
    data: InspectionSetupUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    insp = await _verify_inspection(db, inspection_id, current_user.company_id)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(insp, field, val)
    await db.commit()
    await db.refresh(insp)
    return _inspection_out(insp)


# ── QA Release Gate (Section 7) ───────────────────────────────────────────────────

class QAReviewAction(BaseModel):
    action: str   # approve | reject | release
    notes: Optional[str] = None


@router.post("/{inspection_id}/requests/{request_id}/qa", response_model=dict)
async def qa_action_request(
    inspection_id: str,
    request_id: str,
    data: QAReviewAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """QA approve / reject / release a request. Gate before documents reach the inspector."""
    await _verify_inspection(db, inspection_id, current_user.company_id)

    req_result = await db.execute(
        select(InspectionRequest).where(
            InspectionRequest.id == request_id,
            InspectionRequest.inspection_id == inspection_id,
        )
    )
    req = req_result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    now = datetime.utcnow().isoformat()
    if data.action == "send_to_qa":
        req.status = "qa_review"
    elif data.action == "approve":
        req.status = "approved"
        req.qa_reviewed_by = current_user.id
        req.qa_reviewed_at = now
        req.qa_notes = data.notes
    elif data.action == "reject":
        req.status = "in_progress"
        req.qa_reviewed_by = current_user.id
        req.qa_reviewed_at = now
        req.qa_notes = data.notes
    elif data.action == "release":
        if req.status not in ("approved", "qa_review"):
            raise HTTPException(status_code=400, detail="Request must be QA-approved before release")
        req.status = "released"
        req.released_by = current_user.id
        req.released_at = now
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {data.action}")

    await db.commit()
    await db.refresh(req)
    out = _request_out(req)
    await ws_broadcast(inspection_id, {"type": "request_update", "inspection_id": inspection_id,
                                        "request_id": req.id, "status": req.status,
                                        "fulfillment_progress": req.fulfillment_progress})
    return out


# ── Evidence Package Builder (Section 6) ─────────────────────────────────────────

class PackageCreate(BaseModel):
    title: str
    description: Optional[str] = None
    request_id: Optional[str] = None
    legal_review_required: bool = False
    dual_approval_required: bool = False


class PackageUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    qa_notes: Optional[str] = None
    release_notes: Optional[str] = None
    legal_review_required: Optional[bool] = None
    dual_approval_required: Optional[bool] = None


def _pkg_out(pkg: InspectionEvidencePackage) -> dict:
    return {
        "id": pkg.id,
        "inspection_id": pkg.inspection_id,
        "request_id": pkg.request_id,
        "title": pkg.title,
        "description": pkg.description,
        "status": pkg.status,
        "documents": pkg.documents or [],
        "package_risk": pkg.package_risk,
        "completeness_status": pkg.completeness_status,
        "owner_name": pkg.owner_name,
        "qa_approver_name": pkg.qa_approver_name,
        "qa_approved_at": pkg.qa_approved_at,
        "qa_notes": pkg.qa_notes,
        "qa_checks": pkg.qa_checks or {},
        "released_by_name": pkg.released_by_name,
        "released_at": pkg.released_at,
        "release_notes": pkg.release_notes,
        "legal_review_required": pkg.legal_review_required,
        "dual_approval_required": pkg.dual_approval_required,
        "created_at": str(pkg.created_at),
    }


@router.post("/{inspection_id}/packages", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_evidence_package(
    inspection_id: str,
    data: PackageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    pkg = InspectionEvidencePackage(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_id=data.request_id,
        title=data.title,
        description=data.description,
        owner_id=current_user.id,
        owner_name=current_user.full_name or current_user.email,
        legal_review_required=data.legal_review_required,
        dual_approval_required=data.dual_approval_required,
    )
    db.add(pkg)
    await db.commit()
    await db.refresh(pkg)
    return _pkg_out(pkg)


@router.get("/{inspection_id}/packages", response_model=dict)
async def list_evidence_packages(
    inspection_id: str,
    request_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    filters = [InspectionEvidencePackage.inspection_id == inspection_id]
    if request_id:
        filters.append(InspectionEvidencePackage.request_id == request_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(*filters)
        .order_by(InspectionEvidencePackage.created_at.desc())
    )
    pkgs = result.scalars().all()
    return {"inspection_id": inspection_id, "packages": [_pkg_out(p) for p in pkgs]}


@router.patch("/{inspection_id}/packages/{package_id}", response_model=dict)
async def update_evidence_package(
    inspection_id: str,
    package_id: str,
    data: PackageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(
            InspectionEvidencePackage.id == package_id,
            InspectionEvidencePackage.inspection_id == inspection_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(pkg, field, val)
    await db.commit()
    await db.refresh(pkg)
    return _pkg_out(pkg)


@router.post("/{inspection_id}/packages/{package_id}/documents", response_model=dict)
async def add_document_to_package(
    inspection_id: str,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    filename: str = "",
    document_id: Optional[str] = None,
    version: Optional[str] = None,
    approval_status: Optional[str] = None,
    flags: Optional[dict] = None,
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(
            InspectionEvidencePackage.id == package_id,
            InspectionEvidencePackage.inspection_id == inspection_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    doc_entry = {
        "id": generate_uuid(),
        "filename": filename,
        "document_id": document_id,
        "version": version,
        "approval_status": approval_status or "unknown",
        "flags": flags or {},
        "added_by": current_user.full_name or current_user.email,
        "added_at": datetime.utcnow().isoformat(),
    }
    docs = list(pkg.documents or [])
    docs.append(doc_entry)
    pkg.documents = docs
    pkg.completeness_status = "complete" if docs else "incomplete"
    await db.commit()
    await db.refresh(pkg)
    return _pkg_out(pkg)


@router.delete("/{inspection_id}/packages/{package_id}/documents/{doc_id}", response_model=dict)
async def remove_document_from_package(
    inspection_id: str,
    package_id: str,
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(
            InspectionEvidencePackage.id == package_id,
            InspectionEvidencePackage.inspection_id == inspection_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    pkg.documents = [d for d in (pkg.documents or []) if d.get("id") != doc_id]
    await db.commit()
    await db.refresh(pkg)
    return _pkg_out(pkg)


@router.post("/{inspection_id}/packages/{package_id}/submit-qa", response_model=dict)
async def submit_package_for_qa(
    inspection_id: str,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(
            InspectionEvidencePackage.id == package_id,
            InspectionEvidencePackage.inspection_id == inspection_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    pkg.status = "qa_review"
    await db.commit()
    await db.refresh(pkg)
    await ws_broadcast(inspection_id, {"type": "package_qa_pending", "package_id": package_id, "title": pkg.title})
    return _pkg_out(pkg)


class PackageQAAction(BaseModel):
    action: str   # approve | reject | release
    notes: Optional[str] = None
    qa_checks: Optional[dict] = None


@router.post("/{inspection_id}/packages/{package_id}/qa", response_model=dict)
async def qa_action_package(
    inspection_id: str,
    package_id: str,
    data: PackageQAAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionEvidencePackage).where(
            InspectionEvidencePackage.id == package_id,
            InspectionEvidencePackage.inspection_id == inspection_id,
        )
    )
    pkg = result.scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    now = datetime.utcnow().isoformat()
    if data.action == "approve":
        pkg.status = "approved"
        pkg.qa_approver_id = current_user.id
        pkg.qa_approver_name = current_user.full_name or current_user.email
        pkg.qa_approved_at = now
        pkg.qa_notes = data.notes
        if data.qa_checks:
            pkg.qa_checks = data.qa_checks
    elif data.action == "reject":
        pkg.status = "returned"
        pkg.qa_notes = data.notes
    elif data.action == "release":
        if pkg.status != "approved":
            raise HTTPException(status_code=400, detail="Package must be QA-approved before release")
        pkg.status = "released"
        pkg.released_by_id = current_user.id
        pkg.released_by_name = current_user.full_name or current_user.email
        pkg.released_at = now
        pkg.release_notes = data.notes
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {data.action}")

    await db.commit()
    await db.refresh(pkg)
    await ws_broadcast(inspection_id, {"type": "package_status_update", "package_id": package_id,
                                        "status": pkg.status, "title": pkg.title})
    return _pkg_out(pkg)


# ── SME Coach (Section 11) ────────────────────────────────────────────────────────

class SMECreate(BaseModel):
    name: str
    title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    topics: list[str] = []
    backup_for: Optional[str] = None
    notes: Optional[str] = None


class SMEUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    room: Optional[str] = None
    availability: Optional[str] = None
    topics: Optional[list[str]] = None
    prep_status: Optional[str] = None
    approved_talking_points: Optional[list[str]] = None
    do_not_volunteer: Optional[list[str]] = None
    do_not_speculate: Optional[list[str]] = None
    escalation_triggers: Optional[list[str]] = None
    likely_questions: Optional[list[dict]] = None
    relevant_documents: Optional[list[str]] = None
    known_weak_areas: Optional[str] = None
    notes: Optional[str] = None


def _sme_out(s: InspectionSME) -> dict:
    return {
        "id": s.id,
        "inspection_id": s.inspection_id,
        "name": s.name,
        "title": s.title,
        "department": s.department,
        "email": s.email,
        "phone": s.phone,
        "room": s.room,
        "availability": s.availability,
        "topics": s.topics or [],
        "backup_for": s.backup_for,
        "prep_status": s.prep_status,
        "qa_cleared": s.qa_cleared,
        "qa_cleared_at": s.qa_cleared_at,
        "approved_talking_points": s.approved_talking_points or [],
        "do_not_volunteer": s.do_not_volunteer or [],
        "do_not_speculate": s.do_not_speculate or [],
        "escalation_triggers": s.escalation_triggers or [],
        "likely_questions": s.likely_questions or [],
        "relevant_documents": s.relevant_documents or [],
        "known_weak_areas": s.known_weak_areas,
        "call_log": s.call_log or [],
        "notes": s.notes,
        "created_at": str(s.created_at),
    }


@router.post("/{inspection_id}/smes", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_sme(
    inspection_id: str,
    data: SMECreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    sme = InspectionSME(
        id=generate_uuid(),
        inspection_id=inspection_id,
        **data.model_dump(),
    )
    db.add(sme)
    await db.commit()
    await db.refresh(sme)
    return _sme_out(sme)


@router.get("/{inspection_id}/smes", response_model=dict)
async def list_smes(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(InspectionSME.inspection_id == inspection_id)
        .order_by(InspectionSME.name)
    )
    smes = result.scalars().all()
    return {"inspection_id": inspection_id, "smes": [_sme_out(s) for s in smes]}


@router.patch("/{inspection_id}/smes/{sme_id}", response_model=dict)
async def update_sme(
    inspection_id: str,
    sme_id: str,
    data: SMEUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(
            InspectionSME.id == sme_id,
            InspectionSME.inspection_id == inspection_id,
        )
    )
    sme = result.scalar_one_or_none()
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(sme, field, val)
    await db.commit()
    await db.refresh(sme)
    await ws_broadcast(inspection_id, {"type": "sme_update", "sme_id": sme_id,
                                        "name": sme.name, "availability": sme.availability})
    return _sme_out(sme)


@router.delete("/{inspection_id}/smes/{sme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sme(
    inspection_id: str,
    sme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(
            InspectionSME.id == sme_id,
            InspectionSME.inspection_id == inspection_id,
        )
    )
    sme = result.scalar_one_or_none()
    if sme:
        await db.delete(sme)
        await db.commit()


@router.post("/{inspection_id}/smes/{sme_id}/qa-clear", response_model=dict)
async def qa_clear_sme(
    inspection_id: str,
    sme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(
            InspectionSME.id == sme_id,
            InspectionSME.inspection_id == inspection_id,
        )
    )
    sme = result.scalar_one_or_none()
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found")
    sme.qa_cleared = not sme.qa_cleared
    sme.qa_cleared_by = current_user.id if sme.qa_cleared else None
    sme.qa_cleared_at = datetime.utcnow().isoformat() if sme.qa_cleared else None
    if sme.qa_cleared:
        sme.prep_status = "qa_cleared"
    await db.commit()
    await db.refresh(sme)
    await ws_broadcast(inspection_id, {"type": "sme_update", "sme_id": sme_id,
                                        "name": sme.name, "qa_cleared": sme.qa_cleared})
    return _sme_out(sme)


@router.post("/{inspection_id}/smes/{sme_id}/coach", response_model=dict)
async def ai_coach_sme(
    inspection_id: str,
    sme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI generates coaching brief: talking points, do-not-volunteer, likely questions."""
    from app.engines.llm_engine import _call_llm, _llm_available
    import json, re

    insp = await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(
            InspectionSME.id == sme_id,
            InspectionSME.inspection_id == inspection_id,
        )
    )
    sme = result.scalar_one_or_none()
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found")

    if not _llm_available():
        raise HTTPException(status_code=503, detail="LLM not available")

    prompt = f"""You are a regulatory preparation coach with 20 years of FDA inspection experience.

Generate a coaching brief for an SME who is about to be interviewed by an {insp.agency or "FDA"} inspector.

SME: {sme.name}
Department: {sme.department or "Unknown"}
Topics: {", ".join(sme.topics or ["General quality"]) or "General quality"}
Inspection type: {insp.inspection_type or "routine"}
Sector: {insp.sector or "pharmaceutical"}

Return valid JSON with exactly these keys:
{{
  "approved_talking_points": ["...", "...", "..."],
  "do_not_volunteer": ["topic1", "topic2"],
  "do_not_speculate": ["area1", "area2"],
  "escalation_triggers": ["if asked about X, say you will verify and contact QA"],
  "likely_questions": [
    {{"question": "...", "recommended_answer": "..."}}
  ]
}}

Keep talking points concise and factual. Do-not-volunteer should be areas that could open new inspection scope.
"""

    raw = await _call_llm(prompt, max_tokens=2000)
    try:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        coaching = json.loads(match.group()) if match else {}
    except Exception:
        coaching = {}

    for field in ("approved_talking_points", "do_not_volunteer", "do_not_speculate",
                  "escalation_triggers", "likely_questions"):
        if field in coaching:
            setattr(sme, field, coaching[field])

    await db.commit()
    await db.refresh(sme)
    return _sme_out(sme)


@router.post("/{inspection_id}/smes/{sme_id}/call-log", response_model=dict)
async def log_sme_call(
    inspection_id: str,
    sme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reason: str = "",
    notes: str = "",
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionSME).where(
            InspectionSME.id == sme_id,
            InspectionSME.inspection_id == inspection_id,
        )
    )
    sme = result.scalar_one_or_none()
    if not sme:
        raise HTTPException(status_code=404, detail="SME not found")
    log = list(sme.call_log or [])
    log.append({
        "called_at": datetime.utcnow().isoformat(),
        "called_by": current_user.full_name or current_user.email,
        "reason": reason,
        "notes": notes,
    })
    sme.call_log = log
    await db.commit()
    await db.refresh(sme)
    return _sme_out(sme)


# ── CAPA / Post-Inspection Actions (Section 16) ───────────────────────────────────

class CAPACreate(BaseModel):
    title: str
    description: Optional[str] = None
    action_type: str = "capa"
    owner_name: Optional[str] = None
    department: Optional[str] = None
    due_date: Optional[str] = None
    criticality: str = "medium"
    linked_observation_id: Optional[str] = None
    linked_request_id: Optional[str] = None
    linked_commitment_id: Optional[str] = None
    linked_potential_finding_id: Optional[str] = None
    effectiveness_check_required: bool = False
    management_review_required: bool = False


class CAPAUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    owner_name: Optional[str] = None
    department: Optional[str] = None
    due_date: Optional[str] = None
    criticality: Optional[str] = None
    status: Optional[str] = None
    completion_notes: Optional[str] = None
    effectiveness_check_notes: Optional[str] = None
    lesson_learned: Optional[str] = None
    qms_record_id: Optional[str] = None


def _capa_out(c: InspectionCAPA) -> dict:
    return {
        "id": c.id,
        "inspection_id": c.inspection_id,
        "action_type": c.action_type,
        "title": c.title,
        "description": c.description,
        "owner_name": c.owner_name,
        "department": c.department,
        "due_date": c.due_date,
        "completed_at": c.completed_at,
        "verified_at": c.verified_at,
        "status": c.status,
        "criticality": c.criticality,
        "completion_notes": c.completion_notes,
        "effectiveness_check_required": c.effectiveness_check_required,
        "effectiveness_check_due": c.effectiveness_check_due,
        "effectiveness_check_notes": c.effectiveness_check_notes,
        "management_review_required": c.management_review_required,
        "linked_observation_id": c.linked_observation_id,
        "linked_request_id": c.linked_request_id,
        "linked_commitment_id": c.linked_commitment_id,
        "linked_potential_finding_id": c.linked_potential_finding_id,
        "lesson_learned": c.lesson_learned,
        "qms_exported": c.qms_exported,
        "qms_record_id": c.qms_record_id,
        "created_at": str(c.created_at),
    }


@router.post("/{inspection_id}/capas", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_capa(
    inspection_id: str,
    data: CAPACreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    capa = InspectionCAPA(
        id=generate_uuid(),
        inspection_id=inspection_id,
        created_by=current_user.id,
        **data.model_dump(),
    )
    db.add(capa)
    await db.commit()
    await db.refresh(capa)
    return _capa_out(capa)


@router.get("/{inspection_id}/capas", response_model=dict)
async def list_capas(
    inspection_id: str,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    filters = [InspectionCAPA.inspection_id == inspection_id]
    if status_filter:
        filters.append(InspectionCAPA.status == status_filter)
    result = await db.execute(
        select(InspectionCAPA).where(*filters).order_by(InspectionCAPA.created_at.desc())
    )
    capas = result.scalars().all()
    return {"inspection_id": inspection_id, "capas": [_capa_out(c) for c in capas]}


@router.patch("/{inspection_id}/capas/{capa_id}", response_model=dict)
async def update_capa(
    inspection_id: str,
    capa_id: str,
    data: CAPAUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionCAPA).where(
            InspectionCAPA.id == capa_id,
            InspectionCAPA.inspection_id == inspection_id,
        )
    )
    capa = result.scalar_one_or_none()
    if not capa:
        raise HTTPException(status_code=404, detail="CAPA not found")
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(capa, field, val)
    if data.status == "completed" and not capa.completed_at:
        capa.completed_at = datetime.utcnow().isoformat()
    if data.status == "verified" and not capa.verified_at:
        capa.verified_at = datetime.utcnow().isoformat()
    await db.commit()
    await db.refresh(capa)
    return _capa_out(capa)


@router.delete("/{inspection_id}/capas/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capa(
    inspection_id: str,
    capa_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)
    result = await db.execute(
        select(InspectionCAPA).where(
            InspectionCAPA.id == capa_id,
            InspectionCAPA.inspection_id == inspection_id,
        )
    )
    capa = result.scalar_one_or_none()
    if capa:
        await db.delete(capa)
        await db.commit()


# ── Command Center Metrics (Section 2) ────────────────────────────────────────────

@router.get("/{inspection_id}/metrics", response_model=dict)
async def get_inspection_metrics(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Live command center metrics — all counters for the 'are we in control?' panel."""
    insp = await _verify_inspection(db, inspection_id, current_user.company_id)

    # Requests
    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id)
    )
    requests = req_result.scalars().all()
    total_req = len(requests)
    open_req = sum(1 for r in requests if r.status in ("open", "triage", "assigned", "in_progress", "evidence_gathering"))
    qa_review_req = sum(1 for r in requests if r.status == "qa_review")
    approved_req = sum(1 for r in requests if r.status == "approved")
    released_req = sum(1 for r in requests if r.status == "released")
    fulfilled_req = sum(1 for r in requests if r.status in ("fulfilled", "closed"))
    critical_req = sum(1 for r in requests if r.criticality == "critical" and r.status not in ("fulfilled", "closed", "declined"))
    overdue_req = sum(1 for r in requests if r.due_at and r.status not in ("fulfilled", "closed", "declined", "released")
                      and r.due_at < datetime.utcnow().isoformat())

    # Avg response time
    response_times = [r.response_time_minutes for r in requests if r.response_time_minutes]
    avg_response = int(sum(response_times) / len(response_times)) if response_times else None

    # Commitments
    comm_result = await db.execute(
        select(InspectionCommitment).where(InspectionCommitment.inspection_id == inspection_id)
    )
    commitments = comm_result.scalars().all()
    open_commitments = sum(1 for c in commitments if c.status in ("open", "in_progress"))
    overdue_commitments = sum(1 for c in commitments if c.deadline_at and
                              c.status not in ("fulfilled", "closed") and
                              c.deadline_at < datetime.utcnow().isoformat())

    # Potential findings
    pf_result = await db.execute(
        select(InspectionPotentialFinding).where(InspectionPotentialFinding.inspection_id == inspection_id)
    )
    findings = pf_result.scalars().all()
    active_findings = sum(1 for f in findings if f.status == "tracking")
    high_confidence_findings = sum(1 for f in findings if f.confidence in ("high", "certain") and f.status == "tracking")

    # Packages
    pkg_result = await db.execute(
        select(InspectionEvidencePackage).where(InspectionEvidencePackage.inspection_id == inspection_id)
    )
    packages = pkg_result.scalars().all()
    staged_packages = sum(1 for p in packages if p.status in ("staged", "qa_review"))
    released_packages = sum(1 for p in packages if p.status == "released")

    # SMEs
    sme_result = await db.execute(
        select(InspectionSME).where(InspectionSME.inspection_id == inspection_id)
    )
    smes = sme_result.scalars().all()
    available_smes = sum(1 for s in smes if s.availability == "available")
    qa_cleared_smes = sum(1 for s in smes if s.qa_cleared)

    completion_pct = int((fulfilled_req / total_req * 100)) if total_req else 0

    # "Are we in control?" — simple heuristic
    risk_score = (overdue_req * 3) + (critical_req * 2) + (high_confidence_findings * 2) + (overdue_commitments * 2) + (qa_review_req)
    if risk_score == 0:
        control_status = "in_control"
    elif risk_score <= 3:
        control_status = "manageable"
    elif risk_score <= 8:
        control_status = "under_pressure"
    else:
        control_status = "critical"

    return {
        "inspection_id": inspection_id,
        "requests": {
            "total": total_req, "open": open_req, "qa_review": qa_review_req,
            "approved": approved_req, "released": released_req, "fulfilled": fulfilled_req,
            "critical": critical_req, "overdue": overdue_req,
            "completion_pct": completion_pct, "avg_response_minutes": avg_response,
        },
        "commitments": {
            "total": len(commitments), "open": open_commitments, "overdue": overdue_commitments,
        },
        "findings": {
            "active": active_findings, "high_confidence": high_confidence_findings,
        },
        "packages": {
            "staged": staged_packages, "released": released_packages,
        },
        "smes": {
            "total": len(smes), "available": available_smes, "qa_cleared": qa_cleared_smes,
        },
        "control_status": control_status,
        "risk_score": risk_score,
        "current_phase": insp.current_phase,
        "day_count": insp.day_count,
    }


# ── Daily Briefing (Section 2 / 13) ──────────────────────────────────────────────

@router.post("/{inspection_id}/daily-brief", response_model=dict)
async def generate_daily_brief(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI generates the morning briefing for today's inspection session."""
    from app.engines.llm_engine import _call_llm, _llm_available

    insp = await _verify_inspection(db, inspection_id, current_user.company_id)

    if not _llm_available():
        raise HTTPException(status_code=503, detail="LLM not available")

    # Gather open items
    req_result = await db.execute(
        select(InspectionRequest)
        .where(InspectionRequest.inspection_id == inspection_id,
               InspectionRequest.status.in_(["open", "in_progress", "qa_review", "evidence_gathering"]))
        .order_by(InspectionRequest.criticality.desc())
        .limit(20)
    )
    open_reqs = req_result.scalars().all()

    pf_result = await db.execute(
        select(InspectionPotentialFinding)
        .where(InspectionPotentialFinding.inspection_id == inspection_id,
               InspectionPotentialFinding.status == "tracking")
    )
    findings = pf_result.scalars().all()

    comm_result = await db.execute(
        select(InspectionCommitment)
        .where(InspectionCommitment.inspection_id == inspection_id,
               InspectionCommitment.status.in_(["open", "in_progress"]))
    )
    open_commitments = comm_result.scalars().all()

    context = f"""INSPECTION: {insp.title}
AGENCY: {insp.agency or "FDA"}
PHASE: {insp.current_phase or "Unknown"}
DAY: {insp.day_count or 1}

OPEN REQUESTS ({len(open_reqs)}):
{chr(10).join(f"- [{r.criticality}] {r.request_text[:100]}" for r in open_reqs[:10])}

POTENTIAL FINDINGS ({len(findings)}):
{chr(10).join(f"- [{f.confidence}] {f.title}" for f in findings)}

OPEN COMMITMENTS ({len(open_commitments)}):
{chr(10).join(f"- {c.commitment_text[:80]}" for c in open_commitments[:5])}
"""

    brief = await _call_llm(
        f"""You are a senior inspection host. Generate a concise morning briefing for Day {insp.day_count or 1} of this {insp.agency or "FDA"} inspection.

{context}

Write a crisp morning briefing (3-5 bullet sections) covering:
1. Where we stand — overall posture
2. What to expect today — likely inspector focus based on patterns
3. Top 3 priorities for the team
4. Who needs to be ready
5. One key risk to watch

Keep it tight, no fluff. This is read in 90 seconds by the host team.""",
        max_tokens=800,
    )

    insp.last_daily_brief = brief
    insp.last_daily_brief_at = datetime.utcnow().isoformat()
    await db.commit()

    return {"inspection_id": inspection_id, "brief": brief, "generated_at": insp.last_daily_brief_at}


# ── Post-Inspection Workspace (Section 18) ────────────────────────────────────────

class PostInspectionUpdate(BaseModel):
    outcome: Optional[str] = None
    final_483_count: Optional[int] = None
    post_inspection_notes: Optional[str] = None
    lessons_learned: Optional[list[str]] = None


@router.patch("/{inspection_id}/post-inspection", response_model=dict)
async def update_post_inspection(
    inspection_id: str,
    data: PostInspectionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    insp = await _verify_inspection(db, inspection_id, current_user.company_id)
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(insp, field, val)
    await db.commit()
    await db.refresh(insp)
    return _inspection_out(insp)


@router.get("/{inspection_id}/post-inspection-summary", response_model=dict)
async def get_post_inspection_summary(
    inspection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full post-inspection reconciliation: requests, deliveries, commitments, 483s, CAPAs."""
    insp = await _verify_inspection(db, inspection_id, current_user.company_id)

    req_result = await db.execute(select(InspectionRequest).where(InspectionRequest.inspection_id == inspection_id))
    requests = req_result.scalars().all()

    comm_result = await db.execute(select(InspectionCommitment).where(InspectionCommitment.inspection_id == inspection_id))
    commitments = comm_result.scalars().all()

    obs_result = await db.execute(select(InspectionObservation).where(InspectionObservation.inspection_id == inspection_id))
    observations = obs_result.scalars().all()

    capa_result = await db.execute(select(InspectionCAPA).where(InspectionCAPA.inspection_id == inspection_id))
    capas = capa_result.scalars().all()

    pkg_result = await db.execute(select(InspectionEvidencePackage).where(InspectionEvidencePackage.inspection_id == inspection_id))
    packages = pkg_result.scalars().all()

    return {
        "inspection_id": inspection_id,
        "title": insp.title,
        "agency": insp.agency,
        "outcome": insp.outcome,
        "final_483_count": insp.final_483_count,
        "post_inspection_notes": insp.post_inspection_notes,
        "lessons_learned": insp.lessons_learned or [],
        "requests": {
            "total": len(requests),
            "fulfilled": sum(1 for r in requests if r.status in ("fulfilled", "closed")),
            "unfulfilled": sum(1 for r in requests if r.status not in ("fulfilled", "closed", "declined", "withdrawn")),
        },
        "commitments": {
            "total": len(commitments),
            "fulfilled": sum(1 for c in commitments if c.status in ("fulfilled", "closed")),
            "open": sum(1 for c in commitments if c.status in ("open", "in_progress")),
        },
        "observations": {
            "total": len(observations),
            "draft": sum(1 for o in observations if o.status == "draft"),
            "final": sum(1 for o in observations if o.status == "final"),
            "responded": sum(1 for o in observations if o.status == "responded"),
        },
        "capas": {
            "total": len(capas),
            "open": sum(1 for c in capas if c.status in ("open", "in_progress")),
            "completed": sum(1 for c in capas if c.status in ("completed", "verified", "closed")),
        },
        "packages": {
            "total": len(packages),
            "released": sum(1 for p in packages if p.status == "released"),
        },
    }


# ── Backroom Chat ────────────────────────────────────────────────────────────────

class ChatMessageCreate(BaseModel):
    content: str
    room: str = "all"           # all | front | back | prep
    message_type: str = "general"  # general | sme_call | clarification | urgent
    linked_request_id: Optional[str] = None
    linked_commitment_id: Optional[str] = None


@router.post("/{inspection_id}/chat", response_model=dict, status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    inspection_id: str,
    data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    msg = InspectionMessage(
        id=generate_uuid(),
        inspection_id=inspection_id,
        sender_id=current_user.id,
        sender_name=current_user.full_name or current_user.email,
        content=data.content.strip(),
        room=data.room,
        message_type=data.message_type,
        linked_request_id=data.linked_request_id,
        linked_commitment_id=data.linked_commitment_id,
        is_internal=True,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    payload = {
        "id": msg.id,
        "inspection_id": inspection_id,
        "sender_id": msg.sender_id,
        "sender_name": msg.sender_name,
        "content": msg.content,
        "room": msg.room,
        "message_type": msg.message_type,
        "linked_request_id": msg.linked_request_id,
        "linked_commitment_id": msg.linked_commitment_id,
        "converted_to_request_id": msg.converted_to_request_id,
        "created_at": str(msg.created_at),
    }
    await ws_broadcast(inspection_id, {"type": "chat_message", **payload})
    return payload


@router.get("/{inspection_id}/chat", response_model=dict)
async def list_chat_messages(
    inspection_id: str,
    room: Optional[str] = None,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_inspection(db, inspection_id, current_user.company_id)

    filters = [InspectionMessage.inspection_id == inspection_id]
    if room and room != "all":
        from sqlalchemy import or_
        filters.append(
            or_(InspectionMessage.room == room, InspectionMessage.room == "all")
        )

    result = await db.execute(
        select(InspectionMessage)
        .where(*filters)
        .order_by(InspectionMessage.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    return {
        "inspection_id": inspection_id,
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_name": m.sender_name,
                "content": m.content,
                "room": m.room,
                "message_type": m.message_type,
                "linked_request_id": m.linked_request_id,
                "linked_commitment_id": m.linked_commitment_id,
                "converted_to_request_id": m.converted_to_request_id,
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
    }


@router.post("/{inspection_id}/chat/{message_id}/convert", response_model=dict)
async def convert_chat_to_request(
    inspection_id: str,
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote a chat message to an InspectionRequest."""
    insp = await _verify_inspection(db, inspection_id, current_user.company_id)

    msg_result = await db.execute(
        select(InspectionMessage).where(
            InspectionMessage.id == message_id,
            InspectionMessage.inspection_id == inspection_id,
        )
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.converted_to_request_id:
        raise HTTPException(status_code=409, detail="Already converted")

    # Count existing requests for sequential numbering
    count_res = await db.execute(
        select(func.count()).select_from(InspectionRequest)
        .where(InspectionRequest.inspection_id == inspection_id)
    )
    req_count = count_res.scalar_one() or 0

    new_req = InspectionRequest(
        id=generate_uuid(),
        inspection_id=inspection_id,
        request_number=req_count + 1,
        request_text=msg.content,
        criticality="medium",
        category="question",
        assigned_to=current_user.id,
        assigned_to_name=current_user.full_name or current_user.email,
    )
    db.add(new_req)

    msg.converted_to_request_id = new_req.id
    insp.total_requests = (insp.total_requests or 0) + 1

    await db.commit()
    await db.refresh(new_req)

    await ws_broadcast(inspection_id, {
        "type": "request_created",
        "inspection_id": inspection_id,
        "request_id": new_req.id,
        "from_chat": True,
    })

    return {"request_id": new_req.id, "request_number": new_req.request_number}


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
