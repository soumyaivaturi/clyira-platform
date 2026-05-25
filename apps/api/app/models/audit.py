"""AuditLog model — immutable record of all significant platform events (21 CFR Part 11 §11.10(e))."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, event
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, nullable=False, index=True)
    user_id = Column(String)
    user_email = Column(String)

    # Event classification
    event_type = Column(String(100), nullable=False, index=True)
    # login_success, login_failed, account_locked, logout, terms_accepted, password_changed
    # document_uploaded, assessment_run, finding_resolved, finding_disputed, document_deleted
    # api_key_created, api_key_revoked, company_updated, user_invited

    action = Column(String(20))  # CREATE | READ | UPDATE | DELETE | AUTH | EXPORT

    # Resource context
    resource_type = Column(String(50))
    resource_id = Column(String)
    resource_label = Column(String(500))

    # Change capture — required by Part 11 to record what changed, not just that it changed
    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    detail = Column(JSONB, default=dict)

    # Session and network context
    ip_address = Column(String(45))
    session_id = Column(String(64), nullable=True)

    # Tamper-evident hash — computed from immutable fields at insert time (Part 11 §11.10(e))
    entry_hash = Column(String(64), nullable=True)


@event.listens_for(AuditLog, "before_insert")
def _stamp_audit_hash(mapper, connection, target):  # noqa: ARG001
    from app.services.integrity import compute_hash
    if not target.created_at:
        target.created_at = datetime.now(timezone.utc)
    target.entry_hash = compute_hash({
        "id": target.id,
        "company_id": target.company_id,
        "user_id": target.user_id,
        "user_email": target.user_email,
        "event_type": target.event_type,
        "action": target.action,
        "resource_type": target.resource_type,
        "resource_id": target.resource_id,
        "detail": target.detail,
        "created_at": str(target.created_at),
    })
