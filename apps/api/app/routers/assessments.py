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
    current_level: Optional[str] = None
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
    error_detail: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/recent", response_model=dict)
async def recent_assessments(
    limit: int = Query(default=8, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent completed assessments across all documents for the company."""
    from sqlalchemy import desc as sa_desc
    result = await db.execute(
        select(Assessment, Document.title, Document.document_category)
        .join(Document, Assessment.document_id == Document.id)
        .where(
            Assessment.company_id == current_user.company_id,
            Assessment.status == "completed",
        )
        .order_by(sa_desc(Assessment.created_at))
        .limit(limit)
    )
    rows = []
    for assessment, doc_title, doc_category in result.all():
        rows.append({
            "id": assessment.id,
            "document_id": assessment.document_id,
            "document_title": doc_title,
            "document_category": doc_category,
            "clyira_score": assessment.clyira_score,
            "adjusted_score": assessment.adjusted_score,
            "score_band": assessment.score_band,
            "findings_critical": assessment.findings_critical or 0,
            "findings_high": assessment.findings_high or 0,
            "data_integrity_hold": assessment.data_integrity_hold or False,
            "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
        })
    return {"assessments": rows, "count": len(rows)}


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


class BulkRunRequest(BaseModel):
    document_ids: Optional[list[str]] = None  # None = all un-assessed docs for company
    include_references: bool = True


@router.post("/bulk-run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def bulk_run_assessments(
    data: BulkRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue assessments for multiple documents (or all un-assessed docs if no IDs given)."""
    from sqlalchemy import desc as sa_desc

    if data.document_ids:
        result = await db.execute(
            select(Document).where(
                Document.id.in_(data.document_ids),
                Document.company_id == current_user.company_id,
            )
        )
        docs = result.scalars().all()
    else:
        # All documents that have never been assessed (no completed assessment)
        assessed_subq = (
            select(Assessment.document_id)
            .where(
                Assessment.company_id == current_user.company_id,
                Assessment.status == "completed",
            )
            .distinct()
        )
        result = await db.execute(
            select(Document).where(
                Document.company_id == current_user.company_id,
                Document.status == "ready",
                ~Document.id.in_(assessed_subq),
            )
        )
        docs = result.scalars().all()

    if not docs:
        return {"queued": 0, "assessments": [], "message": "No documents to assess."}

    svc = AssessmentService(db)
    queued = []
    for doc in docs:
        try:
            assessment = await svc.trigger_assessment(
                document_id=doc.id,
                company_id=current_user.company_id,
                user_id=current_user.id,
                include_references=data.include_references,
            )
            background_tasks.add_task(
                _run_assessment_task,
                assessment.id,
                doc.id,
                current_user.company_id,
                data.include_references,
                None,
            )
            queued.append({"assessment_id": assessment.id, "document_id": doc.id, "document_title": doc.title})
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "bulk-run: failed to queue assessment for document %s: %s", doc.id, exc
            )

    return {"queued": len(queued), "assessments": queued, "message": f"Queued {len(queued)} assessment(s)."}


@router.get("/by-document/{document_id}", response_model=dict)
async def get_document_assessment_history(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all completed assessments for a document, oldest first — for score trend charts."""
    from sqlalchemy import asc as sa_asc
    doc_result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == current_user.company_id,
        )
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    result = await db.execute(
        select(Assessment)
        .where(
            Assessment.document_id == document_id,
            Assessment.status == "completed",
        )
        .order_by(sa_asc(Assessment.created_at))
    )
    history = []
    for a in result.scalars().all():
        history.append({
            "id": a.id,
            "clyira_score": a.clyira_score,
            "adjusted_score": a.adjusted_score,
            "score_band": a.score_band,
            "findings_critical": a.findings_critical or 0,
            "findings_high": a.findings_high or 0,
            "findings_medium": a.findings_medium or 0,
            "findings_low": a.findings_low or 0,
            "data_integrity_hold": a.data_integrity_hold or False,
            "dtap_id": a.dtap_id,
            "processing_time_seconds": a.processing_time_seconds,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return {"document_id": document_id, "history": history, "count": len(history)}


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
    # Verify assessment belongs to this user's company before touching any finding
    assessment_check = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    if not assessment_check.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

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
        finding.resolved_at = datetime.utcnow()
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


@router.post("/{assessment_id}/findings/{finding_id}/comments", status_code=201)
async def add_finding_comment(
    assessment_id: str,
    finding_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.assessment import Finding, FindingComment
    # Verify assessment belongs to this user's company
    assessment_check = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    if not assessment_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Assessment not found")

    finding = await db.get(Finding, finding_id)
    if not finding or finding.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Comment text required")

    comment = FindingComment(
        finding_id=finding_id,
        assessment_id=assessment_id,
        user_id=current_user.id,
        user_name=current_user.full_name,
        user_role=current_user.role,
        text=text,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {
        "id": comment.id,
        "finding_id": comment.finding_id,
        "user_name": comment.user_name,
        "user_role": comment.user_role,
        "text": comment.text,
        "created_at": comment.created_at.isoformat(),
    }


@router.get("/{assessment_id}/findings/{finding_id}/comments")
async def get_finding_comments(
    assessment_id: str,
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.assessment import Finding, FindingComment
    from sqlalchemy import select, asc
    # Verify assessment belongs to this user's company
    assessment_check = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    if not assessment_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Assessment not found")

    finding = await db.get(Finding, finding_id)
    if not finding or finding.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    result = await db.execute(
        select(FindingComment)
        .where(FindingComment.finding_id == finding_id)
        .order_by(asc(FindingComment.created_at))
    )
    comments = result.scalars().all()
    return {
        "finding_id": finding_id,
        "comments": [
            {
                "id": c.id,
                "user_name": c.user_name,
                "user_role": c.user_role,
                "text": c.text,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments
        ],
    }


@router.get("/{assessment_id}/report")
async def get_report(
    assessment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full assessment report — document metadata, score summary, findings grouped
    by severity and level, top remediation priorities, and audit-ready metadata.
    """
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    doc = await db.get(Document, assessment.document_id)

    findings_result = await db.execute(
        select(Finding).where(Finding.assessment_id == assessment_id).order_by(Finding.severity)
    )
    findings = findings_result.scalars().all()

    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    sorted_findings = sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.severity, 5))
    finding_dicts = [FindingOut.model_validate(f).model_dump() for f in sorted_findings]

    by_level: dict[str, list] = {}
    for fd in finding_dicts:
        by_level.setdefault(fd["level"], []).append(fd)

    by_severity: dict[str, list] = {}
    for fd in finding_dicts:
        by_severity.setdefault(fd["severity"], []).append(fd)

    top_priority = [
        fd for fd in finding_dicts
        if fd["severity"] in ("critical", "high")
        and fd["status"] in ("open", "acknowledged", "in_progress")
        and fd.get("suggestion_draft")
    ][:10]

    LEVEL_NAMES = {
        "L1": "Structural Integrity", "L2": "Document Control", "L3": "Quality Logic",
        "L4": "ALCOA+ Data Integrity", "L5": "Data & Statistical Intelligence",
        "L6": "Cross-Reference Linkage", "L7": "Lifecycle Compliance",
        "L8": "Regulatory Intelligence", "L9": "Enforcement Pattern Analysis",
        "L10": "Longitudinal Intelligence", "L11": "Submission Readiness",
    }

    return {
        "report_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "assessment_id": assessment_id,
        "document": {
            "id": doc.id if doc else None,
            "title": doc.title if doc else None,
            "document_number": doc.document_number if doc else None,
            "version": doc.version if doc else None,
            "document_category": doc.document_category if doc else None,
            "department_owner": doc.department_owner if doc else None,
            "dtap_id": doc.dtap_id if doc else None,
            "file_type": doc.file_type if doc else None,
        },
        "score_summary": {
            "clyira_score": assessment.clyira_score,
            "adjusted_score": assessment.adjusted_score,
            "score_band": assessment.score_band,
            "data_integrity_hold": assessment.data_integrity_hold or False,
            "suspended_reason": assessment.suspended_reason,
            "enforcement_matches": assessment.enforcement_matches or 0,
            "processing_time_seconds": assessment.processing_time_seconds,
            "levels_run": assessment.levels_run or [],
            "assessed_at": assessment.created_at.isoformat() if assessment.created_at else None,
        },
        "finding_summary": {
            "total": len(findings),
            "critical": assessment.findings_critical or 0,
            "high": assessment.findings_high or 0,
            "medium": assessment.findings_medium or 0,
            "low": assessment.findings_low or 0,
            "info": assessment.findings_info or 0,
            "open": sum(1 for f in findings if f.status == "open"),
            "resolved": sum(1 for f in findings if f.status == "resolved"),
            "in_progress": sum(1 for f in findings if f.status == "in_progress"),
        },
        "findings_by_severity": by_severity,
        "findings_by_level": {
            lv: {"level_name": LEVEL_NAMES.get(lv, lv), "findings": fds}
            for lv, fds in by_level.items()
        },
        "top_remediation_priorities": top_priority,
        "enforcement_findings": [fd for fd in finding_dicts if fd.get("enforcement_match")],
        "all_findings": finding_dicts,
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


@router.post("/{assessment_id}/retry", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_assessment(
    assessment_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retry a failed assessment, resuming from its last completed checkpoint.
    If last_completed_level is set, completed phases are skipped and their findings
    are reused — only failed/remaining phases are re-run.
    """
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status not in ("failed",):
        raise HTTPException(status_code=400, detail="Only failed assessments can be retried")

    checkpoint = assessment.last_completed_level

    background_tasks.add_task(
        _run_assessment_task,
        assessment_id=assessment_id,
        document_id=assessment.document_id,
        company_id=assessment.company_id,
        include_references=assessment.include_references or True,
        regulatory_frameworks=None,
    )

    return {
        "assessment_id": assessment_id,
        "status": "queued",
        "resuming_from_checkpoint": checkpoint,
        "message": (
            f"Retrying from checkpoint '{checkpoint}' — completed phases will be skipped."
            if checkpoint else
            "Retrying from scratch — no checkpoint was saved."
        ),
    }
