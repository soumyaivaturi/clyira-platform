"""
Assessment Engine Router — Triggers and manages document assessments (L1–L11)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.assessment import Assessment, Finding
from app.models.document import Document
from app.models.user import User
from app.services.assessment_service import AssessmentService

router = APIRouter()


class RunAssessmentRequest(BaseModel):
    document_id: str
    include_references: bool = True
    agencies: list[str] = []


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
    status: str
    confidence_score: Optional[float] = None
    validated: bool = False

    class Config:
        from_attributes = True


class AssessmentOut(BaseModel):
    id: str
    document_id: str
    status: str
    clyira_score: Optional[float] = None
    score_band: Optional[str] = None
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    findings_info: int = 0
    enforcement_matches: int = 0
    processing_time_seconds: Optional[float] = None
    levels_run: Optional[list] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("/run", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def run_assessment(
    data: RunAssessmentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a full L1-L11 assessment for a document."""
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


@router.patch("/{assessment_id}/findings/{finding_id}", response_model=dict)
async def respond_to_finding(
    assessment_id: str,
    finding_id: str,
    response_text: str,
    finding_status: str = "acknowledged",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    if finding_status not in valid_statuses:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Status must be one of: {valid_statuses}")

    finding.status = finding_status
    finding.response_text = response_text

    return {"finding_id": finding_id, "status": finding_status, "updated": True}


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
        "score_band": assessment.score_band,
        "findings": [FindingOut.model_validate(f).model_dump() for f in findings],
        "summary": {
            "critical": assessment.findings_critical,
            "high": assessment.findings_high,
            "medium": assessment.findings_medium,
            "low": assessment.findings_low,
            "info": assessment.findings_info,
        },
    }
