"""
Assessment Engine Router — Triggers and manages document assessments (L1–L11)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.dependencies import get_current_user
from app.models.assessment import Assessment, Finding
from app.models.document import Document
from app.models.user import User
from app.services.assessment_service import AssessmentService

router = APIRouter()


async def _run_assessment_task(
    assessment_id: str,
    document_id: str,
    company_id: str,
    include_references: bool,
    regulatory_frameworks: Optional[list],
) -> None:
    async with AsyncSessionLocal() as db:
        svc = AssessmentService(db)
        await svc.run_assessment_background(
            assessment_id=assessment_id,
            document_id=document_id,
            company_id=company_id,
            include_references=include_references,
            regulatory_frameworks=regulatory_frameworks,
        )


class RunAssessmentRequest(BaseModel):
    document_id: str
    include_references: bool = True
    regulatory_frameworks: list[str] = []  # overrides document-level selection when non-empty


class FindingOut(BaseModel):
    id: str
    level: str
    level_name: Optional[str] = None
    severity: str
    category: Optional[str] = None
    title: str
    description: str
    evidence: Optional[str] = None
    location: Optional[str] = None
    regulatory_citation: Optional[str] = None
    citation_type: Optional[str] = None
    agency: Optional[str] = None
    enforcement_match: bool = False
    enforcement_context: Optional[str] = None
    severity_elevated: bool = False
    suggestion_draft: Optional[str] = None
    next_step_text: Optional[str] = None
    remediation_priority: Optional[int] = None
    status: str
    response_text: Optional[str] = None
    dispute_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    validated: bool = False

    class Config:
        from_attributes = True


class AssessmentOut(BaseModel):
    id: str
    document_id: str
    status: str
    clyira_score: Optional[float] = None
    adjusted_score: Optional[float] = None
    score_band: Optional[str] = None
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    findings_info: int = 0
    enforcement_matches: int = 0
    data_integrity_hold: bool = False
    suspended_reason: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    levels_run: Optional[list] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("/run", response_model=AssessmentOut, status_code=status.HTTP_202_ACCEPTED)
async def run_assessment(
    data: RunAssessmentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full L1-L11 assessment. Returns immediately; poll GET /{id} for completion."""
    result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.company_id == current_user.company_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    svc = AssessmentService(db)
    assessment = await svc.trigger_assessment(
        document_id=data.document_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
        include_references=data.include_references,
        regulatory_frameworks=data.regulatory_frameworks or None,
    )

    background_tasks.add_task(
        _run_assessment_task,
        assessment.id,
        data.document_id,
        current_user.company_id,
        data.include_references,
        data.regulatory_frameworks or None,
    )

    return AssessmentOut.model_validate(assessment)


@router.get("/{assessment_id}", response_model=AssessmentOut)
async def get_assessment(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return AssessmentOut.model_validate(assessment)


@router.get("/{assessment_id}/findings", response_model=dict)
async def get_findings(
    assessment_id: str,
    severity: Optional[str] = None,
    level: Optional[str] = None,
    finding_status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    query = select(Finding).where(Finding.assessment_id == assessment_id)
    if severity:
        query = query.where(Finding.severity == severity)
    if level:
        query = query.where(Finding.level == level)
    if finding_status:
        query = query.where(Finding.status == finding_status)

    query = query.order_by(Finding.severity)
    result = await db.execute(query)
    findings = result.scalars().all()

    return {
        "assessment_id": assessment_id,
        "findings": [FindingOut.model_validate(f).model_dump() for f in findings],
        "total": len(findings),
    }


class FindingActionRequest(BaseModel):
    finding_status: str
    response_text: Optional[str] = ""
    dispute_reason: Optional[str] = ""


@router.patch("/{assessment_id}/findings/{finding_id}", response_model=dict)
async def action_finding(
    assessment_id: str,
    finding_id: str,
    data: FindingActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update finding status (acknowledge / in_progress / resolve / dispute) and recompute adjusted score."""
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.assessment_id == assessment_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    valid_statuses = {"open", "acknowledged", "in_progress", "resolved", "disputed"}
    if data.finding_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status must be one of: {valid_statuses}",
        )

    prev_status = finding.status
    finding.status = data.finding_status
    if data.response_text:
        finding.response_text = data.response_text
    if data.dispute_reason:
        finding.dispute_reason = data.dispute_reason
    if data.finding_status == "resolved":
        from datetime import datetime
        finding.resolved_at = datetime.utcnow().isoformat()
    finding.actioned_by = current_user.id
    await db.commit()

    # Recompute adjusted score
    svc = AssessmentService(db)
    new_score = await svc.recompute_adjusted_score(assessment_id)

    # Audit log
    try:
        assessment_row = await db.get(Assessment, assessment_id)
        await svc.write_audit_log(
            company_id=current_user.company_id,
            user_id=current_user.id,
            user_email=current_user.email,
            event_type=f"finding_{data.finding_status}",
            resource_type="finding",
            resource_id=finding_id,
            resource_label=finding.title,
            detail={
                "from_status": prev_status,
                "to_status": data.finding_status,
                "assessment_id": assessment_id,
                "adjusted_score": new_score,
                "dispute_reason": data.dispute_reason or None,
            },
        )
        await db.commit()
    except Exception:
        pass

    return {
        "finding_id": finding_id,
        "status": data.finding_status,
        "adjusted_score": new_score,
        "updated": True,
    }


@router.get("/{assessment_id}/report")
async def get_report(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    findings_result = await db.execute(
        select(Finding).where(Finding.assessment_id == assessment_id).order_by(Finding.severity)
    )
    findings = findings_result.scalars().all()

    return {
        "assessment_id": assessment_id,
        "score": assessment.clyira_score,
        "adjusted_score": assessment.adjusted_score,
        "score_band": assessment.score_band,
        "data_integrity_hold": assessment.data_integrity_hold or False,
        "suspended_reason": assessment.suspended_reason,
        "findings": [FindingOut.model_validate(f).model_dump() for f in findings],
        "summary": {
            "critical": assessment.findings_critical,
            "high": assessment.findings_high,
            "medium": assessment.findings_medium,
            "low": assessment.findings_low,
            "info": assessment.findings_info,
        },
    }


@router.get("/{assessment_id}/live-score", response_model=dict)
async def get_live_score(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recompute score from current finding statuses (reflects resolved/in-progress findings)."""
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    svc = AssessmentService(db)
    new_score = await svc.recompute_adjusted_score(assessment_id)
    return {
        "assessment_id": assessment_id,
        "adjusted_score": new_score,
        "initial_score": assessment.clyira_score,
    }
