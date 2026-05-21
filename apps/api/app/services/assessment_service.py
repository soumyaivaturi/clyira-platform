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
        Trigger a new assessment for a document.
        Creates assessment record and runs the pipeline.
        """
        # Load document
        document = await self.db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Load company
        company = await self.db.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")

        # Create assessment record
        assessment = Assessment(
            document_id=document_id,
            company_id=company_id,
            triggered_by=user_id,
            status="running",
            dtap_id=document.dtap_id,
            include_references=include_references,
            agencies_assessed=company.agencies or [],
        )
        self.db.add(assessment)
        await self.db.commit()
        await self.db.refresh(assessment)

        # Build context
        context = await self._build_context(document, company, assessment, include_references, regulatory_frameworks)

        # Run assessment
        try:
            results = await self.orchestrator.run_assessment(context)

            # Store findings
            await self._store_findings(assessment.id, results["findings"])

            # Update assessment with results
            assessment.status = "completed"
            assessment.clyira_score = results["score"]
            assessment.score_band = results["score_band"]
            assessment.findings_critical = results["finding_counts"]["critical"]
            assessment.findings_high = results["finding_counts"]["high"]
            assessment.findings_medium = results["finding_counts"]["medium"]
            assessment.findings_low = results["finding_counts"]["low"]
            assessment.findings_info = results["finding_counts"]["info"]
            assessment.enforcement_matches = results["enforcement_matches"]
            assessment.processing_time_seconds = results["processing_time_seconds"]
            assessment.levels_run = results["levels_run"]
            assessment.model_version = settings.GEMINI_MODEL

            # Update document latest score
            document.latest_score = results["score"]
            document.latest_assessment_id = assessment.id
            document.status = "assessed"

            await self.db.commit()
            return assessment

        except Exception as e:
            logger.error(f"Assessment failed: {e}")
            assessment.status = "failed"
            await self.db.commit()
            raise

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
        )

    async def _store_findings(self, assessment_id: str, findings: list[FindingResult]):
        """Persist findings to database"""
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
                status="open",
            )
            self.db.add(db_finding)

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
