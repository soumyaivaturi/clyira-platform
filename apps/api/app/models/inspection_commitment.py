"""Verbal commitments made to inspectors — legally significant, must be tracked."""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionCommitment(Base, TimestampMixin):
    __tablename__ = "inspection_commitments"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)
    request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)

    commitment_text = Column(Text, nullable=False)
    committed_by = Column(String(255))   # SME/staff name
    committed_to = Column(String(255))   # Inspector name
    deadline_at = Column(String(50))     # ISO datetime string

    status = Column(String(20), default="pending")  # pending | delivered | overdue
    delivered_at = Column(String(50))
    delivery_note = Column(Text)

    created_by = Column(String, ForeignKey("users.id"))
