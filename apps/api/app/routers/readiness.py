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
    Generate an AI-powered mock FDA/EMA inspection based on the document corpus state.
    Uses the LLM engine + BM25 enforcement patterns for realistic inspection questions.
    """
    from app.models.assessment import Assessment, Finding
    from sqlalchemy import select, desc

    svc = ReadinessService(db)
    readiness = await svc.calculate_company_readiness(current_user.company_id)
    gaps = await svc.get_gap_analysis(current_user.company_id)

    # Gather top critical/high findings from recent assessments
    recent_findings_result = await db.execute(
        select(Finding)
        .join(Assessment, Finding.assessment_id == Assessment.id)
        .where(
            Assessment.company_id == current_user.company_id,
            Assessment.status == "completed",
            Finding.severity.in_(["critical", "high"]),
            Finding.status.in_(["open", "acknowledged"]),
        )
        .order_by(desc(Assessment.created_at))
        .limit(20)
    )
    top_findings = recent_findings_result.scalars().all()

    # Build rule-based questions first
    questions = []
    for gap in gaps["gaps"]["poor_scores"][:3]:
        questions.append({
            "category": "Document Quality",
            "question": f"Walk me through your {gap['category']} document '{gap['title']}'. "
                        f"Clyira score {gap['score']:.1f} — what corrective actions are underway?",
            "criticality": "high",
            "related_document": gap["document_id"],
            "regulatory_basis": "21 CFR 211.100",
        })
    for gap in gaps["gaps"]["missing_assessments"][:2]:
        questions.append({
            "category": "Documentation Gap",
            "question": f"Your {gap['category']} '{gap['title']}' has not been assessed against current GMP requirements. "
                        f"How do you assure its adequacy?",
            "criticality": "medium",
            "related_document": gap["document_id"],
            "regulatory_basis": "21 CFR 211.68",
        })

    # LLM-generated questions based on top open findings
    if top_findings:
        try:
            from app.engines.llm_engine import _call_llm, _llm_available
            if _llm_available():
                finding_summaries = "\n".join(
                    f"- [{f.level}] {f.severity.upper()}: {f.title} ({f.regulatory_citation or 'N/A'})"
                    for f in top_findings[:10]
                )
                system = """You are an FDA investigator conducting a GMP inspection.
Generate 5 pointed inspection questions based on the findings provided.
Each question should probe the root cause, CAPA adequacy, or systemic issue behind the finding.
Return a JSON array: [{"category": "...", "question": "...", "criticality": "high|medium", "regulatory_basis": "21 CFR ..."}]"""

                user = f"""Company readiness score: {readiness['company_score']:.1f}
Open findings that need explanation:
{finding_summaries}

Generate 5 realistic FDA inspection questions. Return ONLY the JSON array."""

                text = await _call_llm(system, user)
                import json
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                llm_questions = json.loads(text.strip())
                for q in llm_questions[:5]:
                    if q.get("question"):
                        q["related_document"] = None
                        q["source"] = "ai_generated"
                        questions.append(q)
        except Exception:
            pass

    # BM25 top enforcement patterns → inspection questions
    try:
        from app.engines import rag_engine
        if rag_engine._load_index() and rag_engine._cfr_freq:
            top_cfr = sorted(rag_engine._cfr_freq.items(), key=lambda x: x[1], reverse=True)[:3]
            for cfr, freq in top_cfr:
                questions.append({
                    "category": "Enforcement Pattern",
                    "question": f"{cfr} appears in {freq} FDA Warning Letters. "
                                f"What controls do you have in place to ensure compliance with {cfr}?",
                    "criticality": "high" if freq >= 45 else "medium",
                    "related_document": None,
                    "regulatory_basis": cfr,
                    "observation_count": freq,
                    "source": "enforcement_pattern",
                })
    except Exception:
        pass

    if not questions:
        questions = [{
            "category": "General",
            "question": "Describe your document control system and how you ensure all quality documents are current, reviewed, and accessible to personnel.",
            "criticality": "medium",
            "related_document": None,
            "regulatory_basis": "21 CFR 211.68",
        }]

    return {
        "simulation_id": f"mock-{current_user.company_id[:8]}",
        "status": "completed",
        "readiness_score": readiness["company_score"],
        "data_integrity_holds": readiness.get("data_integrity_holds", 0),
        "questions": questions[:12],
        "question_count": len(questions[:12]),
        "departments_assessed": [d["department"] for d in readiness["departments"]],
    }


@router.get("/enforcement-alerts")
async def get_enforcement_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enforcement intelligence: DB records + BM25 top-cited CFR patterns.
    Falls back to BM25 corpus patterns when DB enforcement table is empty.
    """
    from app.models.regulatory import EnforcementRecord
    from sqlalchemy import select

    result = await db.execute(
        select(EnforcementRecord)
        .where(EnforcementRecord.trending == True)
        .order_by(EnforcementRecord.created_at.desc())
        .limit(10)
    )
    records = result.scalars().all()
    alerts = [
        {
            "id": r.id,
            "agency": r.agency,
            "record_type": r.record_type,
            "title": r.title,
            "summary": r.summary,
            "issue_date": r.issue_date,
            "pattern_tags": r.pattern_tags or [],
            "trending": r.trending,
            "source": "enforcement_db",
        }
        for r in records
    ]

    # Supplement/replace with BM25 top patterns (FDA Warning Letter observations)
    try:
        from app.engines import rag_engine
        if rag_engine._load_index() and rag_engine._cfr_freq:
            top_cfr = sorted(rag_engine._cfr_freq.items(), key=lambda x: x[1], reverse=True)[:8]
            for cfr, freq in top_cfr:
                # Search for a representative excerpt for this CFR
                precedents = rag_engine.search(cfr, n_results=1, cfr_filter=cfr)
                excerpt = precedents[0].get("text", "")[:200] if precedents else ""
                alerts.append({
                    "id": f"bm25-{cfr}",
                    "agency": "FDA",
                    "record_type": "warning_letter_pattern",
                    "title": f"Recurring Issue: {cfr}",
                    "summary": f"{freq} FDA Warning Letter observations cite {cfr}. {excerpt}",
                    "issue_date": None,
                    "pattern_tags": [cfr],
                    "trending": True,
                    "observation_count": freq,
                    "source": "bm25_corpus",
                })
    except Exception:
        pass

    # Sort: DB records first, then BM25 by frequency
    alerts.sort(key=lambda a: (0 if a.get("source") == "enforcement_db" else 1, -(a.get("observation_count", 0))))

    return {
        "company_id": current_user.company_id,
        "alerts": alerts[:12],
        "total": len(alerts),
    }
