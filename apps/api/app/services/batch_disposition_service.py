"""
Batch Disposition Service.
Computes disposition readiness status for a BatchDossier based on gate checks,
finding states, and evidence completeness. Does NOT make disposition recommendations —
it assesses readiness. The human QA Approver makes the final decision.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch_dossier import BatchDossier, BatchDossierDocument
from app.models.assessment import Assessment, Finding
from app.services.evidence_completeness_service import EvidenceCompletenessService


class BatchDispositionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.completeness_svc = EvidenceCompletenessService()

    async def compute_readiness(self, dossier_id: str) -> dict:
        """
        Compute the full readiness status for a dossier.
        Called after any document assessment completes (micro-batching pattern).
        Updates the dossier's readiness fields in the database.
        """
        dossier = await self.db.get(BatchDossier, dossier_id)
        if not dossier:
            return {"error": "Dossier not found"}

        # Load dossier documents
        docs_result = await self.db.execute(
            select(BatchDossierDocument).where(BatchDossierDocument.dossier_id == dossier_id)
        )
        dossier_docs = docs_result.scalars().all()

        # Evidence completeness
        ev = self.completeness_svc.check(dossier, dossier_docs)
        dossier.gate_evidence_complete = ev["complete"]

        # Load all findings across dossier documents
        document_ids = [dd.document_id for dd in dossier_docs]
        all_findings: list[Finding] = []
        all_assessments: list[Assessment] = []
        scores: list[float] = []

        for doc_id in document_ids:
            result = await self.db.execute(
                select(Assessment)
                .where(Assessment.document_id == doc_id)
                .where(Assessment.status == "completed")
                .order_by(Assessment.created_at.desc())
                .limit(1)
            )
            assessment = result.scalar_one_or_none()
            if not assessment:
                continue
            all_assessments.append(assessment)
            if assessment.clyira_score is not None:
                scores.append(assessment.clyira_score)

            findings_result = await self.db.execute(
                select(Finding).where(Finding.assessment_id == assessment.id)
            )
            all_findings.extend(findings_result.scalars().all())

        # Aggregate scores — primary BPR gets 2x weight, others 1x
        composite_score = None
        if scores:
            primary_doc_ids = {
                dd.document_id for dd in dossier_docs if dd.role == "primary_bpr"
            }
            weighted_sum = 0.0
            weight_total = 0.0
            for assessment in all_assessments:
                w = 2.0 if assessment.document_id in primary_doc_ids else 1.0
                if assessment.clyira_score is not None:
                    weighted_sum += assessment.clyira_score * w
                    weight_total += w
            composite_score = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

        dossier.readiness_score = composite_score

        # Gate: data integrity hold
        data_integrity_blocked = any(
            getattr(a, "data_integrity_hold", False) for a in all_assessments
        )
        dossier.gate_data_integrity = data_integrity_blocked

        # Gate: all findings addressed
        open_findings = [
            f for f in all_findings
            if f.status in ("open", "disputed", "acknowledged")
        ]
        critical_open = [f for f in open_findings if f.severity == "critical"]
        high_open = [f for f in open_findings if f.severity == "high"]
        dossier.gate_all_findings_addressed = len(open_findings) == 0

        # Gate: gray findings resolved (critical fields only)
        unresolved_gray_critical = [
            f for f in all_findings
            if getattr(f, "verification_state", None) == "gray"
            and getattr(f, "field_criticality", None) in ("critical", "high")
            and f.status in ("open", "acknowledged")
        ]
        dossier.gate_gray_findings_resolved = len(unresolved_gray_critical) == 0

        # Determine readiness status
        readiness = self._compute_readiness_status(
            composite_score=composite_score,
            gate_evidence_complete=dossier.gate_evidence_complete,
            gate_data_integrity=not data_integrity_blocked,
            critical_open=len(critical_open),
            high_open=len(high_open),
            gray_critical_unresolved=len(unresolved_gray_critical),
            evidence_completeness=ev,
        )

        dossier.readiness_status = readiness["status"]
        dossier.readiness_band = readiness["band"]

        # Advance dossier status if under_review and now ready
        if dossier.status == "under_review" and readiness["status"] == "ready":
            dossier.status = "pending_disposition"

        await self.db.commit()

        return {
            "dossier_id": dossier_id,
            "readiness_status": readiness["status"],
            "readiness_band": readiness["band"],
            "readiness_score": composite_score,
            "gates": {
                "evidence_complete": dossier.gate_evidence_complete,
                "data_integrity_ok": not data_integrity_blocked,
                "all_findings_addressed": dossier.gate_all_findings_addressed,
                "gray_findings_resolved": dossier.gate_gray_findings_resolved,
            },
            "finding_summary": {
                "total": len(all_findings),
                "critical_open": len(critical_open),
                "high_open": len(high_open),
                "open_total": len(open_findings),
            },
            "evidence_completeness": ev,
            "readiness_message": readiness["message"],
        }

    def _compute_readiness_status(
        self,
        composite_score: float | None,
        gate_evidence_complete: bool,
        gate_data_integrity: bool,  # True = OK (no hold)
        critical_open: int,
        high_open: int,
        gray_critical_unresolved: int,
        evidence_completeness: dict,
    ) -> dict:
        """
        Determine disposition readiness status based on gates and score.
        Returns status, band, and message.
        """
        # Hard blocks → Not Ready or Hold
        if not gate_data_integrity:
            return {
                "status": "hold",
                "band": "Hold for QA Evaluation",
                "message": "Data integrity concern detected. Human QA evaluation required before proceeding.",
            }

        if critical_open > 0:
            return {
                "status": "not_ready",
                "band": "Not Ready",
                "message": f"{critical_open} critical finding(s) require resolution before disposition review.",
            }

        if gray_critical_unresolved > 0:
            return {
                "status": "not_ready",
                "band": "Not Ready",
                "message": f"{gray_critical_unresolved} unresolved Gray finding(s) on critical fields require human input.",
            }

        if not gate_evidence_complete and evidence_completeness.get("missing_required"):
            return {
                "status": "not_ready",
                "band": "Not Ready",
                "message": f"Evidence package incomplete: {evidence_completeness['summary']}",
            }

        # Score-based readiness
        if composite_score is None:
            return {
                "status": "not_ready",
                "band": "Assessment Pending",
                "message": "No completed assessments found. Run assessment on the primary record first.",
            }

        if composite_score >= 90 and high_open == 0:
            return {
                "status": "ready",
                "band": "Ready for QA Disposition Review",
                "message": "All gates pass and all findings addressed. Dossier is ready for QA disposition review.",
            }
        elif composite_score >= 80:
            return {
                "status": "conditional",
                "band": "Conditional Readiness",
                "message": f"Score {composite_score:.1f} — minor open items present. Document justification before disposition.",
            }
        elif composite_score >= 65:
            return {
                "status": "not_ready",
                "band": "Not Ready",
                "message": f"Score {composite_score:.1f} — significant findings require resolution.",
            }
        else:
            return {
                "status": "hold",
                "band": "Hold for QA Evaluation",
                "message": f"Score {composite_score:.1f} — fundamental quality concerns require QA evaluation.",
            }

    async def record_disposition_decision(
        self,
        dossier_id: str,
        decision: str,
        rationale: str,
        decided_by: str,
        conditional_conditions: list | None = None,
    ) -> dict:
        """Record the human QA Approver's final disposition decision."""
        from datetime import datetime, timezone

        dossier = await self.db.get(BatchDossier, dossier_id)
        if not dossier:
            return {"error": "Dossier not found"}

        dossier.disposition_decision = decision
        dossier.disposition_rationale = rationale
        dossier.released_by = decided_by
        dossier.released_at = datetime.now(timezone.utc).isoformat()

        if conditional_conditions:
            dossier.conditional_release_conditions = {"conditions": conditional_conditions}

        # Flag if human decision diverges from readiness status
        readiness = dossier.readiness_status
        divergent = (
            (decision == "release" and readiness not in ("ready", "conditional"))
            or (decision == "reject" and readiness == "ready")
        )
        dossier.disposition_divergence = divergent

        # Update dossier status
        status_map = {
            "release": "released",
            "conditional_release": "conditionally_released",
            "hold": "on_hold",
            "reject": "rejected",
        }
        dossier.status = status_map.get(decision, dossier.status)

        await self.db.commit()

        return {
            "dossier_id": dossier_id,
            "decision": decision,
            "divergence_flagged": divergent,
            "status": dossier.status,
        }
