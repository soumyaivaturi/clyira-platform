"""AuditLog model — immutable record of all significant platform events."""
from sqlalchemy import Column, String, Text
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
    # e.g. document_uploaded, assessment_run, finding_resolved, finding_disputed,
    #      finding_acknowledged, finding_in_progress, document_deleted

    # Resource context
    resource_type = Column(String(50))  # document, assessment, finding
    resource_id = Column(String)
    resource_label = Column(String(500))  # human-readable label

    # Event detail
    detail = Column(JSONB, default=dict)
    # e.g. {"from_status": "open", "to_status": "resolved", "score_before": 72, "score_after": 78}

    ip_address = Column(String(45))
