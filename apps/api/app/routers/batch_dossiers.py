"""
Batch & Lot Record Review — API Router
Provides CRUD for BatchDossiers, document linking, readiness computation,
disposition decisions, and evidence completeness checks.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.batch_dossier import (
    BatchDossier, BatchDossierDocument, EvidencePackageTemplate, FeedbackCorrection
)
from app.models.assessment import Assessment, Finding
from app.models.document import Document
from app.models.base import generate_uuid
from app.models.user import User
from app.schemas.batch_dossier import (
    BatchDossierCreate, BatchDossierUpdate,
    BatchDossierDocumentAdd, DispositionDecisionCreate,
    FeedbackCorrectionCreate,
)
from app.services.batch_disposition_service import BatchDispositionService
from app.services.evidence_completeness_service import EvidenceCompletenessService

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Serialisers ──────────────────────────────────────────────────────────────

def _dossier_out(d: BatchDossier, documents: list = None, readiness: dict = None) -> dict:
    return {
        "id": d.id,
        "company_id": d.company_id,
        "created_by": d.created_by,
        "lot_number": d.lot_number,
        "product_name": d.product_name,
        "product_code": d.product_code,
        "dosage_form": d.dosage_form,
        "batch_size": d.batch_size,
        "manufacturing_site": d.manufacturing_site,
        "manufacturing_date": d.manufacturing_date,
        "target_release_date": d.target_release_date,
        # Layer 0
        "record_family": d.record_family,
        "product_type": d.product_type,
        "is_sterile": d.is_sterile,
        "manufacturing_context": d.manufacturing_context,
        "batch_purpose": d.batch_purpose,
        "target_markets": d.target_markets or [],
        # Status
        "status": d.status,
        "readiness_status": d.readiness_status,
        "readiness_score": d.readiness_score,
        "readiness_band": d.readiness_band,
        # Disposition
        "disposition_decision": d.disposition_decision,
        "disposition_rationale": d.disposition_rationale,
        "disposition_divergence": d.disposition_divergence,
        "conditional_release_conditions": d.conditional_release_conditions,
        # Gates
        "gates": {
            "evidence_complete": d.gate_evidence_complete,
            "open_deviations": d.gate_open_deviations,
            "open_capas": d.gate_open_capas,
            "qc_complete": d.gate_qc_complete,
            "data_integrity_ok": not d.gate_data_integrity,
            "all_findings_addressed": d.gate_all_findings_addressed,
            "gray_findings_resolved": d.gate_gray_findings_resolved,
        },
        # Review
        "shadow_mode": d.shadow_mode,
        "review_stage": d.review_stage,
        "released_by": d.released_by,
        "released_at": d.released_at,
        "documents": documents or [],
        "readiness_detail": readiness or {},
        "created_at": str(d.created_at),
        "updated_at": str(d.updated_at),
    }


def _dossier_doc_out(dd: BatchDossierDocument) -> dict:
    return {
        "id": dd.id,
        "dossier_id": dd.dossier_id,
        "document_id": dd.document_id,
        "role": dd.role,
        "sequence_order": dd.sequence_order,
        "notes": dd.notes,
        "added_by": dd.added_by,
        "added_at": str(dd.created_at),
    }


def _finding_out(f: Finding) -> dict:
    return {
        "id": f.id,
        "level": f.level,
        "level_name": f.level_name,
        "severity": f.severity,
        "category": f.category,
        "title": f.title,
        "description": f.description,
        "evidence": f.evidence,
        "location": f.location,
        "regulatory_citation": f.regulatory_citation,
        "enforcement_match": f.enforcement_match,
        "suggestion_draft": f.suggestion_draft,
        "status": f.status,
        "confidence_score": f.confidence_score,
        "verification_state": getattr(f, "verification_state", None),
        "field_criticality": getattr(f, "field_criticality", None),
        "source_page": getattr(f, "source_page", None),
        "human_verification_required": getattr(f, "human_verification_required", False),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_dossiers(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all batch dossiers for the current user's company."""
    q = select(BatchDossier).where(BatchDossier.company_id == current_user.company_id)
    if status:
        q = q.where(BatchDossier.status == status)
    q = q.order_by(BatchDossier.created_at.desc())
    result = await db.execute(q)
    dossiers = result.scalars().all()

    output = []
    for d in dossiers:
        docs_result = await db.execute(
            select(BatchDossierDocument).where(BatchDossierDocument.dossier_id == d.id)
        )
        docs = docs_result.scalars().all()
        output.append(_dossier_out(d, [_dossier_doc_out(dd) for dd in docs]))
    return output


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dossier(
    body: BatchDossierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new batch dossier with Layer 0 classification."""
    dossier = BatchDossier(
        id=generate_uuid(),
        company_id=current_user.company_id,
        created_by=current_user.id,
        lot_number=body.lot_number,
        product_name=body.product_name,
        product_code=body.product_code,
        dosage_form=body.dosage_form,
        batch_size=body.batch_size,
        manufacturing_site=body.manufacturing_site,
        manufacturing_date=body.manufacturing_date,
        target_release_date=body.target_release_date,
        record_family=body.record_family,
        product_type=body.product_type,
        is_sterile=body.is_sterile,
        manufacturing_context=body.manufacturing_context,
        batch_purpose=body.batch_purpose,
        target_markets=body.target_markets,
        shadow_mode=body.shadow_mode,
        status="draft",
    )
    db.add(dossier)
    await db.commit()
    await db.refresh(dossier)
    return _dossier_out(dossier)


@router.get("/{dossier_id}")
async def get_dossier(
    dossier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a dossier with full detail: documents, findings, readiness."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    docs_result = await db.execute(
        select(BatchDossierDocument).where(BatchDossierDocument.dossier_id == dossier_id)
    )
    dossier_docs = docs_result.scalars().all()

    # Enrich each dossier document with assessment summary and findings
    enriched_docs = []
    for dd in dossier_docs:
        dd_out = _dossier_doc_out(dd)

        # Load document title
        doc = await db.get(Document, dd.document_id)
        if doc:
            dd_out["document_title"] = doc.title
            dd_out["document_category"] = doc.document_category
            dd_out["document_status"] = doc.status

        # Load latest completed assessment
        assessment_result = await db.execute(
            select(Assessment)
            .where(Assessment.document_id == dd.document_id)
            .where(Assessment.status == "completed")
            .order_by(Assessment.created_at.desc())
            .limit(1)
        )
        assessment = assessment_result.scalar_one_or_none()
        if assessment:
            dd_out["assessment"] = {
                "id": assessment.id,
                "clyira_score": assessment.clyira_score,
                "score_band": assessment.score_band,
                "findings_critical": assessment.findings_critical,
                "findings_high": assessment.findings_high,
                "findings_medium": assessment.findings_medium,
                "findings_low": assessment.findings_low,
                "completed_at": assessment.completed_at,
            }

            # Load findings for this document
            findings_result = await db.execute(
                select(Finding).where(Finding.assessment_id == assessment.id)
                .order_by(Finding.severity)
            )
            findings = findings_result.scalars().all()
            dd_out["findings"] = [_finding_out(f) for f in findings]
        else:
            dd_out["assessment"] = None
            dd_out["findings"] = []

        enriched_docs.append(dd_out)

    # Evidence completeness
    svc = EvidenceCompletenessService()
    ev_check = svc.check(dossier, dossier_docs)

    return _dossier_out(dossier, enriched_docs, ev_check)


@router.patch("/{dossier_id}")
async def update_dossier(
    dossier_id: str,
    body: BatchDossierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update dossier metadata or Layer 0 classification."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dossier, field, value)

    await db.commit()
    await db.refresh(dossier)
    return _dossier_out(dossier)


@router.delete("/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dossier(
    dossier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a draft dossier. Only allowed when status=draft."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")
    if dossier.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft dossiers can be deleted")
    await db.delete(dossier)
    await db.commit()


@router.post("/{dossier_id}/documents")
async def add_document(
    dossier_id: str,
    body: BatchDossierDocumentAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a document to a dossier with a role."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    # Verify document belongs to same company
    doc = await db.get(Document, body.document_id)
    if not doc or doc.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check for duplicate
    existing = await db.execute(
        select(BatchDossierDocument)
        .where(BatchDossierDocument.dossier_id == dossier_id)
        .where(BatchDossierDocument.document_id == body.document_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Document already added to this dossier")

    dd = BatchDossierDocument(
        id=generate_uuid(),
        dossier_id=dossier_id,
        document_id=body.document_id,
        role=body.role,
        sequence_order=body.sequence_order,
        notes=body.notes,
        added_by=current_user.id,
    )
    db.add(dd)

    # Advance status to under_review if still draft
    if dossier.status == "draft":
        dossier.status = "under_review"

    await db.commit()
    await db.refresh(dd)

    # Recompute readiness with new document set
    try:
        svc = BatchDispositionService(db)
        await svc.compute_readiness(dossier_id)
    except Exception as e:
        logger.warning(f"Readiness recompute after add_document failed: {e}")

    return _dossier_doc_out(dd)


@router.delete("/{dossier_id}/documents/{dossier_doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    dossier_id: str,
    dossier_doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a document from a dossier."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    dd = await db.get(BatchDossierDocument, dossier_doc_id)
    if not dd or dd.dossier_id != dossier_id:
        raise HTTPException(status_code=404, detail="Document link not found")

    await db.delete(dd)
    await db.commit()


@router.post("/{dossier_id}/assess-readiness")
async def assess_readiness(
    dossier_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger readiness computation for a dossier.
    This runs the BatchDispositionService and updates all gate flags and readiness status.
    """
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    svc = BatchDispositionService(db)
    result = await svc.compute_readiness(dossier_id)
    return result


@router.post("/{dossier_id}/disposition")
async def record_disposition(
    dossier_id: str,
    body: DispositionDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record the QA Approver's final disposition decision.
    Validates that rationale is provided and flags any divergence from readiness status.
    """
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    if body.decision not in ("release", "conditional_release", "hold", "reject"):
        raise HTTPException(status_code=400, detail="Invalid disposition decision")

    if len(body.rationale.strip()) < 20:
        raise HTTPException(status_code=400, detail="Disposition rationale must be at least 20 characters")

    svc = BatchDispositionService(db)
    result = await svc.record_disposition_decision(
        dossier_id=dossier_id,
        decision=body.decision,
        rationale=body.rationale,
        decided_by=current_user.id,
        conditional_conditions=body.conditional_conditions,
    )
    return result


@router.get("/{dossier_id}/findings")
async def list_dossier_findings(
    dossier_id: str,
    verification_state: str | None = None,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all findings across all documents in a dossier.
    Optionally filter by verification_state (green/red/blue/gray) or severity.
    """
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    docs_result = await db.execute(
        select(BatchDossierDocument).where(BatchDossierDocument.dossier_id == dossier_id)
    )
    dossier_docs = docs_result.scalars().all()

    all_findings = []
    for dd in dossier_docs:
        assessment_result = await db.execute(
            select(Assessment)
            .where(Assessment.document_id == dd.document_id)
            .where(Assessment.status == "completed")
            .order_by(Assessment.created_at.desc())
            .limit(1)
        )
        assessment = assessment_result.scalar_one_or_none()
        if not assessment:
            continue

        findings_q = select(Finding).where(Finding.assessment_id == assessment.id)
        if verification_state:
            findings_q = findings_q.where(Finding.verification_state == verification_state)
        if severity:
            findings_q = findings_q.where(Finding.severity == severity)

        findings_result = await db.execute(findings_q.order_by(Finding.severity))
        findings = findings_result.scalars().all()

        for f in findings:
            f_out = _finding_out(f)
            f_out["document_id"] = dd.document_id
            f_out["document_role"] = dd.role
            all_findings.append(f_out)

    # Sort: critical first, then high, medium, low, info
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    all_findings.sort(key=lambda f: severity_order.get(f["severity"], 5))

    return {
        "dossier_id": dossier_id,
        "total": len(all_findings),
        "findings": all_findings,
    }


@router.post("/{dossier_id}/feedback-correction")
async def submit_feedback_correction(
    dossier_id: str,
    body: FeedbackCorrectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a reviewer correction to an AI-extracted or AI-assessed value."""
    dossier = await db.get(BatchDossier, dossier_id)
    if not dossier or dossier.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Dossier not found")

    correction = FeedbackCorrection(
        id=generate_uuid(),
        finding_id=body.finding_id,
        document_id=body.document_id,
        corrected_by=current_user.id,
        field_name=body.field_name,
        original_value=body.original_value,
        corrected_value=body.corrected_value,
        source_page=body.source_page,
        field_criticality=body.field_criticality,
        correction_rationale=body.correction_rationale,
    )
    db.add(correction)
    await db.commit()
    return {"id": correction.id, "status": "recorded"}


@router.get("/stats/summary")
async def dossier_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dashboard stats: counts by status and readiness for this company."""
    result = await db.execute(
        select(BatchDossier)
        .where(BatchDossier.company_id == current_user.company_id)
    )
    dossiers = result.scalars().all()

    status_counts: dict = {}
    readiness_counts: dict = {}
    for d in dossiers:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1
        if d.readiness_status:
            readiness_counts[d.readiness_status] = readiness_counts.get(d.readiness_status, 0) + 1

    return {
        "total": len(dossiers),
        "by_status": status_counts,
        "by_readiness": readiness_counts,
    }
