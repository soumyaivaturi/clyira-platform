"""
Electronic signatures — 21 CFR Part 11 §11.50, §11.100, §11.200.

§11.200(b) requires that each electronic signature act be accompanied by password
re-authentication at the time of signing. This router enforces that requirement.
"""
import hashlib
from datetime import datetime, timezone
from typing import Literal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.document_signature import DocumentSignature
from app.models.user import User
from app.models.base import generate_uuid

router = APIRouter()

VALID_MEANINGS = {"authored", "reviewed", "approved"}


class SignRequest(BaseModel):
    meaning: Literal["authored", "reviewed", "approved"]
    password: str  # §11.200(b) — re-authentication at time of signing


class SignatureOut(BaseModel):
    id: str
    document_id: str
    user_id: str
    user_full_name: str
    user_email: str
    user_role: str
    meaning: str
    document_version: str | None
    document_content_hash: str | None
    signed_at: str
    is_voided: bool
    voided_at: str | None
    void_reason: str | None
    entry_hash: str | None


def _ip(request: Request) -> str | None:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return getattr(request.client, "host", None)


async def _audit(db, company_id, user_id, user_email, event_type, resource_id, detail, ip):
    log = AuditLog(
        id=generate_uuid(),
        company_id=company_id,
        user_id=user_id,
        user_email=user_email,
        event_type=event_type,
        action="CREATE",
        resource_type="document_signature",
        resource_id=resource_id,
        detail=detail or {},
        ip_address=ip,
    )
    try:
        async with db.begin_nested():
            db.add(log)
            await db.flush()
    except Exception:
        pass


@router.post("/{document_id}/signatures", response_model=SignatureOut, status_code=201)
async def sign_document(
    document_id: str,
    body: SignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Electronically sign a document.

    §11.200(b): password re-authentication required per signing event.
    §11.50: captures printed name, date/time, and meaning.
    """
    # 1. Re-authenticate the user's password
    if not bcrypt.checkpw(body.password.encode(), current_user.password_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Incorrect password — electronic signature requires password re-authentication (21 CFR §11.200(b))",
        )

    # 2. Load document and verify ownership
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == current_user.company_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # 3. Hash document content at signing time (immutable record of what was signed)
    content_hash: str | None = None
    if doc.extracted_text:
        content_hash = hashlib.sha256(doc.extracted_text.encode()).hexdigest()

    # 4. Record the signature
    now = datetime.now(timezone.utc)
    sig = DocumentSignature(
        id=generate_uuid(),
        document_id=document_id,
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_full_name=current_user.full_name,
        user_email=current_user.email,
        user_role=current_user.role,
        meaning=body.meaning,
        document_version=doc.version,
        document_content_hash=content_hash,
        ip_address=_ip(request),
        created_at=now,
    )
    db.add(sig)
    await db.flush()

    # 5. Audit trail
    await _audit(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        user_email=current_user.email,
        event_type="document_signed",
        resource_id=sig.id,
        detail={
            "document_id": document_id,
            "document_title": doc.title,
            "meaning": body.meaning,
            "document_version": doc.version,
            "content_hash": content_hash,
            "signer_role": current_user.role,
            "cfr_basis": "21 CFR Part 11 §11.50, §11.100, §11.200",
        },
        ip=_ip(request),
    )
    await db.commit()
    await db.refresh(sig)

    return SignatureOut(
        id=sig.id,
        document_id=sig.document_id,
        user_id=sig.user_id,
        user_full_name=sig.user_full_name,
        user_email=sig.user_email,
        user_role=sig.user_role,
        meaning=sig.meaning,
        document_version=sig.document_version,
        document_content_hash=sig.document_content_hash,
        signed_at=sig.created_at.isoformat() if sig.created_at else now.isoformat(),
        is_voided=sig.is_voided,
        voided_at=sig.voided_at.isoformat() if sig.voided_at else None,
        void_reason=sig.void_reason,
        entry_hash=sig.entry_hash,
    )


@router.get("/{document_id}/signatures", response_model=list[SignatureOut])
async def list_signatures(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all signatures for a document (active + voided)."""
    # Verify document belongs to this company
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == current_user.company_id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(DocumentSignature)
        .where(DocumentSignature.document_id == document_id)
        .order_by(DocumentSignature.created_at)
    )
    sigs = result.scalars().all()

    return [
        SignatureOut(
            id=s.id,
            document_id=s.document_id,
            user_id=s.user_id,
            user_full_name=s.user_full_name,
            user_email=s.user_email,
            user_role=s.user_role,
            meaning=s.meaning,
            document_version=s.document_version,
            document_content_hash=s.document_content_hash,
            signed_at=s.created_at.isoformat() if s.created_at else "",
            is_voided=s.is_voided,
            voided_at=s.voided_at.isoformat() if s.voided_at else None,
            void_reason=s.void_reason,
            entry_hash=s.entry_hash,
        )
        for s in sigs
    ]
