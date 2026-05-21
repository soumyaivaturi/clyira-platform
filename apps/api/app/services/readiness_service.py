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
        1. Per-document scores (from assessments)
        2. Per-department aggregate
        3. Company-level aggregate
        """
        # Load all assessed documents for this company
        result = await self.db.execute(
            select(Document).where(
                Document.company_id == company_id,
                Document.latest_score.isnot(None),
            )
        )
        documents = result.scalars().all()

        # Group by department
        dept_documents: dict[str, list] = {}
        for doc in documents:
            dept = doc.department_owner or "Unassigned"
            if dept not in dept_documents:
                dept_documents[dept] = []
            dept_documents[dept].append({"score": doc.latest_score, "weight": 1.0})

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
        }

    async def get_gap_analysis(self, company_id: str, department: Optional[str] = None) -> dict:
        """
        Identify gaps in the document corpus:
        - Missing document types
        - Documents not yet assessed
        - Documents with poor scores
        - Expired/overdue for review
        """
        query = select(Document).where(Document.company_id == company_id)
        if department:
            query = query.where(Document.department_owner == department)

        result = await self.db.execute(query)
        documents = result.scalars().all()

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
            elif doc.latest_score and doc.latest_score < 65.0:
                gaps["poor_scores"].append({
                    "document_id": doc.id,
                    "title": doc.title,
                    "score": doc.latest_score,
                    "category": doc.document_category,
                })

        return {
            "company_id": company_id,
            "department": department,
            "gaps": gaps,
            "total_documents": len(documents),
            "assessed_count": sum(1 for d in documents if d.status == "assessed"),
            "gap_count": sum(len(v) for v in gaps.values()),
        }
