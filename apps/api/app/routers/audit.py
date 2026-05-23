"""
Audit Trail Router — Immutable event log for GxP compliance traceability.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.audit import AuditLog
from app.models.user import User

router = APIRouter()


@router.get("/log", response_model=dict)
async def get_audit_log(
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return audit log events for the current company.
    Filterable by event_type, resource_type, and resource_id.
    """
    query = (
        select(AuditLog)
        .where(AuditLog.company_id == current_user.company_id)
        .order_by(desc(AuditLog.created_at))
    )
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)

    total_q = select(AuditLog).where(AuditLog.company_id == current_user.company_id)
    if event_type:
        total_q = total_q.where(AuditLog.event_type == event_type)
    if resource_type:
        total_q = total_q.where(AuditLog.resource_type == resource_type)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "events": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "resource_label": log.resource_label,
                "user_email": log.user_email,
                "detail": log.detail,
                "created_at": str(log.created_at),
            }
            for log in logs
        ],
        "count": len(logs),
        "offset": offset,
        "limit": limit,
    }


@router.get("/log/{resource_id}", response_model=dict)
async def get_resource_audit_log(
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all audit events for a specific resource (document, assessment, or finding)."""
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.company_id == current_user.company_id,
            AuditLog.resource_id == resource_id,
        )
        .order_by(desc(AuditLog.created_at))
    )
    logs = result.scalars().all()

    return {
        "resource_id": resource_id,
        "events": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "resource_label": log.resource_label,
                "user_email": log.user_email,
                "detail": log.detail,
                "created_at": str(log.created_at),
            }
            for log in logs
        ],
        "count": len(logs),
    }
