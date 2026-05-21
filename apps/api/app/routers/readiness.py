"""
Audit Readiness Router — Module 2
Continuous readiness scoring, gap analysis, mock inspections
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.readiness_service import ReadinessService

router = APIRouter()


@router.get("/dashboard")
async def get_readiness_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Company-level readiness dashboard: scores, department breakdown, top gaps."""
    svc = ReadinessService(db)
    readiness = await svc.calculate_company_readiness(current_user.company_id)
    gaps = await svc.get_gap_analysis(current_user.company_id)

    return {
        **readiness,
        "top_gaps": {
            "missing_assessments": gaps["gaps"]["missing_assessments"][:5],
            "poor_scores": gaps["gaps"]["poor_scores"][:5],
        },
        "gap_count": gaps["gap_count"],
    }


@router.get("/scores")
async def get_scores(
    scope: str = "company",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReadinessService(db)
    readiness = await svc.calculate_company_readiness(current_user.company_id)

    if scope == "department":
        return {"scope": "department", "scores": readiness["departments"]}
    return {"scope": "company", "score": readiness["company_score"], "score_band": readiness["score_band"]}


@router.get("/gaps")
async def get_gap_analysis(
    department: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ReadinessService(db)
    return await svc.get_gap_analysis(current_user.company_id, department)


@router.post("/mock-inspection")
async def create_mock_inspection(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI-powered mock inspection based on document corpus state.
    Requires Anthropic API key for AI-generated questions.
    """
    svc = ReadinessService(db)
    readiness = await svc.calculate_company_readiness(current_user.company_id)
    gaps = await svc.get_gap_analysis(current_user.company_id)

    # Generate mock questions based on current gaps (rule-based for now)
    questions = []
    for gap in gaps["gaps"]["poor_scores"][:3]:
        questions.append({
            "category": "Document Quality",
            "question": f"Walk me through your {gap['category']} document '{gap['title']}'. "
                        f"It has a Clyira score of {gap['score']:.1f}. What corrective actions are in place?",
            "criticality": "high",
            "related_document": gap["document_id"],
        })
    for gap in gaps["gaps"]["missing_assessments"][:3]:
        questions.append({
            "category": "Documentation Gap",
            "question": f"Your {gap['category']} '{gap['title']}' has not been assessed. "
                        f"How do you ensure it meets current regulatory requirements?",
            "criticality": "medium",
            "related_document": gap["document_id"],
        })
    if not questions:
        questions = [
            {
                "category": "General",
                "question": "Describe your document control system and how you ensure all procedures are current.",
                "criticality": "medium",
                "related_document": None,
            }
        ]

    return {
        "simulation_id": f"mock-{current_user.company_id[:8]}",
        "status": "completed",
        "readiness_score": readiness["company_score"],
        "questions": questions,
        "departments_assessed": [d["department"] for d in readiness["departments"]],
    }


@router.get("/enforcement-alerts")
async def get_enforcement_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enforcement intelligence relevant to this company's sub-sectors."""
    from app.models.regulatory import EnforcementRecord
    from sqlalchemy import select

    result = await db.execute(
        select(EnforcementRecord)
        .where(EnforcementRecord.trending == True)
        .order_by(EnforcementRecord.created_at.desc())
        .limit(10)
    )
    records = result.scalars().all()

    return {
        "company_id": current_user.company_id,
        "alerts": [
            {
                "id": r.id,
                "agency": r.agency,
                "record_type": r.record_type,
                "title": r.title,
                "summary": r.summary,
                "issue_date": r.issue_date,
                "pattern_tags": r.pattern_tags or [],
                "trending": r.trending,
            }
            for r in records
        ],
    }
