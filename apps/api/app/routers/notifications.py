"""
Notifications Router — computed alerts from existing quality data (no separate model).
Returns structured alerts for: overdue reviews, DI holds, open critical findings,
upcoming inspections, enforcement matches.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.assessment import Assessment, Finding
from app.models.document import Document
from app.models.user import User

router = APIRouter()

REVIEW_CYCLE_DAYS = {
    "SOP": 730,
    "CAPA": 365,
    "ATM": 730,
    "Deviation": 365,
    "LIR": 365,
    "Validation": 730,
}
DEFAULT_REVIEW_DAYS = 730


@router.get("/alerts", response_model=dict)
async def get_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute and return all active quality alerts for the company.
    Aggregates overdue reviews, DI holds, open critical/high findings,
    and enforcement hits into a unified alert feed.
    """
    now = datetime.now(timezone.utc)
    company_id = current_user.company_id
    alerts = []

    # ── 1. Data integrity holds ──────────────────────────────────────────────
    di_result = await db.execute(
        select(Assessment, Document.title)
        .join(Document, Assessment.document_id == Document.id)
        .where(
            Assessment.company_id == company_id,
            Assessment.status == "completed",
            Assessment.data_integrity_hold == True,
        )
        .order_by(Assessment.created_at.desc())
        .limit(20)
    )
    for assessment, doc_title in di_result.all():
        alerts.append({
            "id": f"di_hold_{assessment.id}",
            "type": "data_integrity_hold",
            "severity": "critical",
            "title": "Data Integrity Hold Active",
            "message": f"{doc_title} has an active Data Integrity hold — score capped at 50.",
            "document_id": assessment.document_id,
            "assessment_id": assessment.id,
            "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
        })

    # ── 2. Open critical findings ────────────────────────────────────────────
    crit_result = await db.execute(
        select(Finding, Assessment.document_id, Document.title)
        .join(Assessment, Finding.assessment_id == Assessment.id)
        .join(Document, Assessment.document_id == Document.id)
        .where(
            Assessment.company_id == company_id,
            Finding.severity == "critical",
            Finding.status.in_(["open", "acknowledged"]),
        )
        .order_by(Finding.remediation_priority)
        .limit(15)
    )
    for finding, doc_id, doc_title in crit_result.all():
        alerts.append({
            "id": f"finding_{finding.id}",
            "type": "open_critical_finding",
            "severity": "critical",
            "title": f"Open Critical Finding: {finding.title}",
            "message": f"{doc_title} — {finding.description[:120]}…" if len(finding.description) > 120 else f"{doc_title} — {finding.description}",
            "document_id": doc_id,
            "assessment_id": finding.assessment_id,
            "finding_id": finding.id,
            "created_at": None,
        })

    # ── 3. Enforcement matches ───────────────────────────────────────────────
    enf_result = await db.execute(
        select(Assessment, Document.title)
        .join(Document, Assessment.document_id == Document.id)
        .where(
            Assessment.company_id == company_id,
            Assessment.status == "completed",
            Assessment.enforcement_matches > 0,
        )
        .order_by(Assessment.enforcement_matches.desc())
        .limit(10)
    )
    for assessment, doc_title in enf_result.all():
        alerts.append({
            "id": f"enforcement_{assessment.id}",
            "type": "enforcement_match",
            "severity": "high",
            "title": f"FDA Enforcement Pattern Match ({assessment.enforcement_matches} hit{'s' if assessment.enforcement_matches != 1 else ''})",
            "message": f"{doc_title} matches {assessment.enforcement_matches} FDA Warning Letter observation pattern(s).",
            "document_id": assessment.document_id,
            "assessment_id": assessment.id,
            "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
        })

    # ── 4. Overdue for re-assessment ─────────────────────────────────────────
    docs_result = await db.execute(
        select(Document).where(Document.company_id == company_id)
    )
    documents = docs_result.scalars().all()
    doc_ids = [d.id for d in documents]
    doc_map = {d.id: d for d in documents}

    if doc_ids:
        latest_result = await db.execute(
            select(Assessment.document_id, func.max(Assessment.created_at).label("last_at"))
            .where(
                Assessment.document_id.in_(doc_ids),
                Assessment.status == "completed",
            )
            .group_by(Assessment.document_id)
        )
        last_assessed: dict[str, datetime] = {}
        for row in latest_result.all():
            ts = row.last_at
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            last_assessed[row.document_id] = ts

        for doc in documents:
            if doc.id not in last_assessed:
                continue
            cycle = REVIEW_CYCLE_DAYS.get(doc.document_category or "", DEFAULT_REVIEW_DAYS)
            age = (now - last_assessed[doc.id]).days
            if age > cycle:
                overdue_by = age - cycle
                alerts.append({
                    "id": f"overdue_{doc.id}",
                    "type": "overdue_review",
                    "severity": "medium",
                    "title": f"Overdue for Re-Assessment ({overdue_by}d)",
                    "message": f"{doc.title} was last assessed {age} days ago. {doc.document_category or 'Document'} review cycle is {cycle} days.",
                    "document_id": doc.id,
                    "assessment_id": None,
                    "created_at": last_assessed[doc.id].isoformat(),
                })

    # ── 5. Open high findings (capped at 10 so list doesn't explode) ─────────
    high_result = await db.execute(
        select(func.count(Finding.id))
        .join(Assessment, Finding.assessment_id == Assessment.id)
        .where(
            Assessment.company_id == company_id,
            Finding.severity == "high",
            Finding.status.in_(["open", "acknowledged"]),
        )
    )
    open_high_count = high_result.scalar() or 0
    if open_high_count > 0:
        alerts.append({
            "id": "open_high_summary",
            "type": "open_high_findings",
            "severity": "high",
            "title": f"{open_high_count} Open High-Severity Finding{'s' if open_high_count != 1 else ''}",
            "message": f"{open_high_count} high-severity findings remain open or acknowledged across your document corpus.",
            "document_id": None,
            "assessment_id": None,
            "created_at": None,
        })

    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: SEVERITY_ORDER.get(a["severity"], 4))

    return {
        "alerts": alerts,
        "total": len(alerts),
        "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
        "high_count": sum(1 for a in alerts if a["severity"] == "high"),
        "medium_count": sum(1 for a in alerts if a["severity"] == "medium"),
    }
