"""
Assessment Service — Orchestrates assessment workflow.
Bridges routers → engines with database persistence.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.document import Document, DocumentReference
from app.models.assessment import Assessment, Finding
from app.models.company import Company
from app.models.regulatory import EnforcementRecord
from app.dtap import DTAPRegistry
from app.engines.orchestrator import AssessmentOrchestrator
from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)


class AssessmentService:
    """Service layer for assessments"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = AssessmentOrchestrator()

    async def trigger_assessment(
        self,
        document_id: str,
        company_id: str,
        user_id: str,
        include_references: bool = True,
        regulatory_frameworks: Optional[list] = None,
    ) -> Assessment:
        """
        Create an assessment record with status='queued' and return immediately.
        The caller is responsible for running the actual pipeline in a background task.
        """
        document = await self.db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        company = await self.db.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        assessment = Assessment(
            document_id=document_id,
            company_id=company_id,
            triggered_by=user_id,
            status="queued",
            dtap_id=document.dtap_id,
            include_references=include_references,
            agencies_assessed=company.agencies or [],
        )
        self.db.add(assessment)
        await self.db.commit()
        await self.db.refresh(assessment)
        return assessment

    async def run_assessment_background(
        self,
        assessment_id: str,
        document_id: str,
        company_id: str,
        include_references: bool = True,
        regulatory_frameworks: Optional[list] = None,
    ) -> None:
        """Run the full L1-L11 pipeline for an existing assessment record."""
        document = await self.db.get(Document, document_id)
        company = await self.db.get(Company, company_id)
        assessment = await self.db.get(Assessment, assessment_id)
        if not all([document, company, assessment]):
            logger.error(f"Background assessment {assessment_id}: missing record(s)")
            return

        assessment.status = "running"
        assessment.current_level = None
        await self.db.commit()

        context = await self._build_context(document, company, assessment, include_references, regulatory_frameworks)

        _db = self.db
        _assessment = assessment

        async def _progress(level: str) -> None:
            _assessment.current_level = level
            try:
                await _db.commit()
            except Exception:
                pass

        try:
            results = await self.orchestrator.run_assessment(context, progress_callback=_progress)
            await self._store_findings(assessment.id, results["findings"])

            assessment.status = "completed"
            assessment.current_level = None
            assessment.clyira_score = results["score"]
            assessment.adjusted_score = results["score"]  # starts equal; updates as findings are resolved
            assessment.score_band = results["score_band"]
            assessment.findings_critical = results["finding_counts"]["critical"]
            assessment.findings_high = results["finding_counts"]["high"]
            assessment.findings_medium = results["finding_counts"]["medium"]
            assessment.findings_low = results["finding_counts"]["low"]
            assessment.findings_info = results["finding_counts"]["info"]
            assessment.enforcement_matches = results["enforcement_matches"]
            assessment.processing_time_seconds = results["processing_time_seconds"]
            assessment.levels_run = results["levels_run"]
            assessment.data_integrity_hold = results.get("data_integrity_hold", False)
            assessment.suspended_reason = results.get("suspended_reason")
            from app.engines.llm_engine import _active_model
            assessment.model_version = _active_model()

            document.latest_score = results["score"]
            document.latest_assessment_id = assessment.id
            document.status = "assessed"

            await self.db.commit()
            logger.info(f"Assessment {assessment_id} completed: score={results['score']}")

            # Audit log
            try:
                await self.write_audit_log(
                    company_id=company_id,
                    user_id=assessment.triggered_by,
                    user_email=None,
                    event_type="assessment_run",
                    resource_type="assessment",
                    resource_id=assessment_id,
                    resource_label=document.title,
                    detail={
                        "score": results["score"],
                        "score_band": results["score_band"],
                        "findings_count": len(results["findings"]),
                        "data_integrity_hold": results.get("data_integrity_hold", False),
                        "dtap_id": assessment.dtap_id,
                    },
                )
                await self.db.commit()
            except Exception:
                pass  # audit log failure must never break an assessment

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Background assessment {assessment_id} failed: {e}\n{tb}")
            print(f"  ASSESSMENT FAILED [{assessment_id}]: {type(e).__name__}: {e}\n{tb}")
            assessment.status = "failed"
            assessment.current_level = None
            assessment.error_detail = f"{type(e).__name__}: {e}\n\n{tb}"
            await self.db.commit()

    async def _build_context(
        self,
        document: Document,
        company: Company,
        assessment: Assessment,
        include_references: bool,
        regulatory_frameworks: Optional[list] = None,
    ) -> AssessmentContext:
        """Build the full context needed for assessment"""
        # Load DTAP
        dtap_profile = DTAPRegistry.get(document.dtap_id) if document.dtap_id else None
        if not dtap_profile and document.document_category:
            dtap_profile = DTAPRegistry.get_by_category(document.document_category)

        # Load user references
        user_references = []
        if include_references:
            result = await self.db.execute(
                select(DocumentReference).where(DocumentReference.document_id == document.id)
            )
            refs = result.scalars().all()
            user_references = [
                {"title": r.title, "extracted_text": r.extracted_text, "reference_type": r.reference_type}
                for r in refs
            ]

        # Load enforcement records for company's sub-sectors
        enforcement_records = []
        if company.sub_sectors:
            result = await self.db.execute(
                select(EnforcementRecord).limit(50)
                # In production: filter by sub_sector overlap and recency
            )
            records = result.scalars().all()
            enforcement_records = [
                {
                    "reference_number": r.reference_number,
                    "record_type": r.record_type,
                    "agency": r.agency,
                    "title": r.title,
                    "summary": r.summary,
                    "observation_categories": r.observation_categories or [],
                    "cfr_citations": r.cfr_citations or [],
                    "company_cited": r.company_cited,
                    "issue_date": r.issue_date,
                    "outcome": r.outcome,
                    "trending": r.trending,
                }
                for r in records
            ]

        # Load historical assessments for this document (for L10 longitudinal analysis)
        historical_assessments = []
        hist_result = await self.db.execute(
            select(Assessment)
            .where(
                Assessment.document_id == document.id,
                Assessment.status == "completed",
                Assessment.id != assessment.id,
            )
            .order_by(Assessment.created_at.desc())
            .limit(5)
        )
        for hist in hist_result.scalars().all():
            findings_result = await self.db.execute(
                select(Finding).where(Finding.assessment_id == hist.id)
            )
            hist_findings = findings_result.scalars().all()
            historical_assessments.append({
                "assessment_id": hist.id,
                "score": hist.clyira_score,
                "score_band": hist.score_band,
                "created_at": hist.created_at.isoformat() if hist.created_at else None,
                "findings": [
                    {
                        "level": f.level,
                        "severity": f.severity,
                        "category": f.category,
                        "title": f.title,
                        "status": f.status,
                    }
                    for f in hist_findings
                ],
            })

        return AssessmentContext(
            document_id=document.id,
            company_id=company.id,
            assessment_id=assessment.id,
            document_text=document.extracted_text or "",
            document_sections=document.extracted_sections or {},
            document_category=document.document_category or "",
            dtap_profile=dtap_profile,
            company_agencies=company.agencies or [],
            company_sub_sectors=company.sub_sectors or [],
            regulatory_frameworks=regulatory_frameworks if regulatory_frameworks is not None else (document.regulatory_frameworks or []),
            user_references=user_references,
            enforcement_records=enforcement_records,
            historical_assessments=historical_assessments,
        )

    async def _store_findings(self, assessment_id: str, findings: list[FindingResult]):
        """Persist findings to database"""
        from app.engines.scoring import ScoringEngine
        for finding in findings:
            db_finding = Finding(
                assessment_id=assessment_id,
                level=finding.level,
                level_name=self._get_level_name(finding.level),
                severity=finding.severity,
                category=finding.category,
                title=finding.title,
                description=finding.description,
                evidence=finding.evidence,
                location=finding.location,
                regulatory_citation=finding.regulatory_citation,
                citation_type=finding.citation_type,
                agency=finding.agency,
                enforcement_match=finding.enforcement_match,
                enforcement_context=finding.enforcement_context,
                severity_elevated=finding.severity_elevated,
                suggestion_draft=finding.suggestion_draft,
                next_step_text=finding.next_step_text,
                validated=finding.validated,
                confidence_score=finding.confidence_score,
                remediation_priority=ScoringEngine.get_remediation_priority(finding.severity),
                status="open",
            )
            self.db.add(db_finding)

        await self.db.flush()

    async def recompute_adjusted_score(self, assessment_id: str) -> float | None:
        """Recompute adjusted_score from current finding statuses and persist to DB."""
        assessment = await self.db.get(Assessment, assessment_id)
        if not assessment:
            return None

        dtap_profile = None
        if assessment.dtap_id:
            from app.dtap import DTAPRegistry
            dtap_profile = DTAPRegistry.get(assessment.dtap_id)
        if not dtap_profile:
            return None

        result = await self.db.execute(
            select(Finding).where(Finding.assessment_id == assessment_id)
        )
        findings = result.scalars().all()
        if not findings:
            return None

        from app.engines.scoring import ScoringEngine
        db_dicts = [
            {"level": f.level, "severity": f.severity, "status": f.status, "title": f.title}
            for f in findings
        ]
        score_result = ScoringEngine().calculate_from_db_findings(db_dicts, dtap_profile)
        new_score = score_result["score"]

        assessment.adjusted_score = new_score
        await self.db.commit()
        return new_score

    async def write_audit_log(
        self,
        company_id: str,
        user_id: str | None,
        user_email: str | None,
        event_type: str,
        resource_type: str,
        resource_id: str,
        resource_label: str = "",
        detail: dict | None = None,
    ) -> None:
        """Write an immutable audit log entry."""
        from app.models.audit import AuditLog
        log = AuditLog(
            company_id=company_id,
            user_id=user_id,
            user_email=user_email,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
            detail=detail or {},
        )
        self.db.add(log)
        await self.db.flush()

    @staticmethod
    def _get_level_name(level: str) -> str:
        names = {
            "L1": "Structural Integrity",
            "L2": "Document Control",
            "L3": "Content Quality",
            "L4": "ALCOA+ Data Integrity",
            "L5": "Data Intelligence",
            "L6": "Cross-Document Consistency",
            "L7": "Lifecycle Compliance",
            "L8": "Regulatory Gap Analysis",
            "L9": "Enforcement Risk",
            "L10": "Longitudinal Intelligence",
            "L11": "Submission Readiness",
        }
        return names.get(level, level)
