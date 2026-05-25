"""DocumentSignature — electronic signatures per 21 CFR Part 11 §11.50, §11.100, §11.200."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, event

from app.models.base import Base, TimestampMixin, generate_uuid


class DocumentSignature(Base, TimestampMixin):
    __tablename__ = "document_signatures"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, nullable=False, index=True)
    company_id = Column(String, nullable=False, index=True)

    # Signer identity — denormalized so the record is self-contained after personnel changes
    user_id = Column(String, nullable=False)
    user_full_name = Column(String(255), nullable=False)
    user_email = Column(String(255), nullable=False)
    user_role = Column(String(50), nullable=False)

    # §11.50(a) — meaning of each signature
    meaning = Column(String(50), nullable=False)  # authored | reviewed | approved

    # Document state at signing time
    document_version = Column(String(20), nullable=True)
    document_content_hash = Column(String(64), nullable=True)  # SHA-256 of extracted_text

    # Network context
    ip_address = Column(String(45), nullable=True)

    # Void workflow (signatures are never deleted — only voided)
    is_voided = Column(Boolean, default=False, nullable=False)
    voided_at = Column(DateTime, nullable=True)
    voided_by = Column(String, nullable=True)
    void_reason = Column(String(500), nullable=True)

    # Tamper-evident hash of this record's immutable fields
    entry_hash = Column(String(64), nullable=True)


def _hash_signature(signature: DocumentSignature) -> str:
    from app.services.integrity import compute_hash
    return compute_hash({
        "id": signature.id,
        "document_id": signature.document_id,
        "company_id": signature.company_id,
        "user_id": signature.user_id,
        "user_email": signature.user_email,
        "meaning": signature.meaning,
        "document_content_hash": signature.document_content_hash,
        "created_at": str(signature.created_at),
    })


@event.listens_for(DocumentSignature, "before_insert")
def _stamp_signature_hash(mapper, connection, target):  # noqa: ARG001
    if not target.created_at:
        target.created_at = datetime.now(timezone.utc)
    target.entry_hash = _hash_signature(target)
