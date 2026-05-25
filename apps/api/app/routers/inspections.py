"""
Real-Time Audit Support Router — Module 3
Live inspection management, AI agents, request board, post-inspection
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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
        "ai_agents_count": len(insp.ai_agents_active) if insp.ai_agents_active else 0,
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
            "ai_talking_points": r.ai_talking_points or [],
            "ai_suggested_documents": r.ai_suggested_documents or [],
            "ai_risk_assessment": r.ai_risk_assessment,
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
    await db.commit()
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
    await db.commit()
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
    await db.commit()
    await db.refresh(req)

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

    await db.commit()
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
    await db.commit()
    await db.refresh(entry)

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


# ── AI Analysis ─────────────────────────────────────────────────────────────────

@router.post("/{inspection_id}/requests/{request_id}/analyze", response_model=dict)
async def analyze_request(
    inspection_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run AI analysis on an inspector request.
    Generates talking points, document suggestions, and a risk assessment.
    Stores results on the request record and returns them.
    """
    from app.models.document import Document
    from app.engines.llm_engine import _llm_available
    import json

    # Verify request belongs to an inspection owned by this company
    req_result = await db.execute(
        select(InspectionRequest).where(InspectionRequest.id == request_id)
    )
    req = req_result.scalar_one_or_none()
    if not req or req.inspection_id != inspection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    insp_result = await db.execute(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.company_id == current_user.company_id,
        )
    )
    if not insp_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Load company document titles for context
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

Available company documents (title, department, readiness score):
{doc_list or "No documents found."}

Respond with a structured JSON object using exactly these keys:
{{
  "talking_points": ["<3-5 concise bullet points of what to say to the inspector>"],
  "suggested_documents": ["<2-3 document titles from the list above most relevant to this request>"],
  "risk_assessment": "<1-2 sentence assessment of the regulatory risk this request represents>"
}}

Be specific and actionable. Reference 21 CFR Part 211 or other applicable regulations where relevant.
Only suggest documents from the provided list. Respond with valid JSON only."""

    try:
        from app.engines.llm_engine import _call_llm
        raw = await _call_llm(
            "You are a pharmaceutical regulatory expert supporting a GMP inspection war room.",
            prompt,
        )
        # Extract JSON from response
        import re
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
