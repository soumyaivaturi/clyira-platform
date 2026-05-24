"""
Readiness Service — Clyira Score aggregation and gap analysis.
Aggregates document scores → department scores → company score.
"""
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.document import Document
from app.models.readiness import ReadinessScore
from app.models.company import Company
from app.engines.scoring import ScoringEngine

logger = logging.getLogger(__name__)

# Default department weights
DEFAULT_DEPARTMENT_WEIGHTS = {
    "Quality Assurance": 0.25,
    "Quality Control": 0.25,
    "Manufacturing": 0.20,
    "Validation": 0.15,
    "Regulatory Affairs": 0.15,
}


class ReadinessService:
    """Service for audit readiness scoring and gap analysis"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scoring = ScoringEngine()

    async def calculate_company_readiness(self, company_id: str) -> dict:
        """
        Calculate full readiness hierarchy:
        1. Per-document scores (adjusted_score preferred over latest_score)
        2. Per-department aggregate
        3. Company-level aggregate
        Also counts data integrity holds and enforcement matches.
        """
        from app.models.assessment import Assessment
        from sqlalchemy import desc

        # Load all assessed documents for this company
        result = await self.db.execute(
            select(Document).where(
                Document.company_id == company_id,
                Document.latest_score.isnot(None),
            )
        )
        documents = result.scalars().all()

        # Load the latest assessment per document to get adjusted scores and hold flags
        assessment_map: dict[str, Assessment] = {}
        doc_ids = [d.id for d in documents]
        if doc_ids:
            a_result = await self.db.execute(
                select(Assessment)
                .where(
                    Assessment.document_id.in_(doc_ids),
                    Assessment.status == "completed",
                )
                .order_by(desc(Assessment.created_at))
            )
            for a in a_result.scalars().all():
                if a.document_id not in assessment_map:
                    assessment_map[a.document_id] = a

        # Group by department — prefer adjusted_score
        dept_documents: dict[str, list] = {}
        data_integrity_holds = 0
        enforcement_match_count = 0

        for doc in documents:
            dept = doc.department_owner or "Unassigned"
            a = assessment_map.get(doc.id)
            score = (a.adjusted_score if a and a.adjusted_score is not None else doc.latest_score) or 0.0
            if a and a.data_integrity_hold:
                data_integrity_holds += 1
            if a and a.enforcement_matches:
                enforcement_match_count += a.enforcement_matches

            if dept not in dept_documents:
                dept_documents[dept] = []
            dept_documents[dept].append({"score": score, "weight": 1.0})

        # Calculate department scores
        department_scores = []
        for dept, doc_scores in dept_documents.items():
            dept_result = self.scoring.calculate_readiness_score(doc_scores)
            dept_weight = DEFAULT_DEPARTMENT_WEIGHTS.get(dept, 0.10)
            department_scores.append({
                "department": dept,
                "score": dept_result["score"],
                "score_band": dept_result["score_band"],
                "weight": dept_weight,
                "document_count": dept_result["document_count"],
            })

        # Calculate company score
        company_score_data = [
            {"score": d["score"], "weight": d["weight"]}
            for d in department_scores
        ]
        company_result = self.scoring.calculate_readiness_score(company_score_data)

        return {
            "company_id": company_id,
            "company_score": company_result["score"],
            "score_band": company_result["score_band"],
            "departments": department_scores,
            "total_documents": len(documents),
            "data_integrity_holds": data_integrity_holds,
            "enforcement_matches_total": enforcement_match_count,
        }

    # Review cycle thresholds by document category (days since last assessment)
    REVIEW_CYCLE_DAYS = {
        "SOP": 730,        # 2 years
        "CAPA": 365,       # 1 year (active CAPAs need annual review)
        "ATM": 730,        # 2 years
        "Deviation": 365,  # 1 year
        "LIR": 365,        # 1 year
        "Validation": 730, # 2 years
    }
    DEFAULT_REVIEW_DAYS = 730

    async def get_gap_analysis(self, company_id: str, department: Optional[str] = None) -> dict:
        """
        Identify gaps in the document corpus:
        - Missing document types
        - Documents not yet assessed
        - Documents with poor scores
        - Expired/overdue for review (based on last assessment age vs. category cycle)
        """
        from datetime import datetime, timezone, timedelta
        from app.models.assessment import Assessment
        from sqlalchemy import desc as sa_desc

        query = select(Document).where(Document.company_id == company_id)
        if department:
            query = query.where(Document.department_owner == department)

        result = await self.db.execute(query)
        documents = result.scalars().all()

        # Load latest assessment date per assessed document
        doc_ids = [d.id for d in documents if d.status == "assessed"]
        last_assessed_map: dict[str, datetime] = {}
        if doc_ids:
            a_result = await self.db.execute(
                select(Assessment.document_id, Assessment.created_at)
                .where(Assessment.document_id.in_(doc_ids), Assessment.status == "completed")
                .order_by(sa_desc(Assessment.created_at))
            )
            for doc_id, created_at in a_result.all():
                if doc_id not in last_assessed_map and created_at:
                    last_assessed_map[doc_id] = created_at

        now = datetime.now(timezone.utc)

        gaps = {
            "missing_assessments": [],
            "poor_scores": [],
            "critical_findings": [],
            "overdue_review": [],
        }

        for doc in documents:
            if doc.status != "assessed":
                gaps["missing_assessments"].append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "category": doc.document_category,
                    "status": doc.status,
                })
            else:
                if doc.latest_score and doc.latest_score < 65.0:
                    gaps["poor_scores"].append({
                        "document_id": doc.id,
                        "title": doc.title,
                        "score": doc.latest_score,
                        "category": doc.document_category,
                    })

                # Check review cycle
                last_assessed = last_assessed_map.get(doc.id)
                if last_assessed:
                    cycle_days = self.REVIEW_CYCLE_DAYS.get(
                        doc.document_category or "", self.DEFAULT_REVIEW_DAYS
                    )
                    last_assessed_tz = last_assessed.replace(tzinfo=timezone.utc) if last_assessed.tzinfo is None else last_assessed
                    age_days = (now - last_assessed_tz).days
                    if age_days > cycle_days:
                        gaps["overdue_review"].append({
                            "document_id": doc.id,
                            "title": doc.title,
                            "category": doc.document_category,
                            "last_assessed_days_ago": age_days,
                            "review_cycle_days": cycle_days,
                            "overdue_by_days": age_days - cycle_days,
                        })

        return {
            "company_id": company_id,
            "department": department,
            "gaps": gaps,
            "total_documents": len(documents),
            "assessed_count": sum(1 for d in documents if d.status == "assessed"),
            "gap_count": sum(len(v) for v in gaps.values()),
        }
