"""FDA 483 Observation workspace — structured response drafting per observation."""
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text

from app.models.base import Base, TimestampMixin, generate_uuid
from sqlalchemy.dialects.postgresql import JSONB


class InspectionObservation(Base, TimestampMixin):
    __tablename__ = "inspection_observations"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)

    observation_number = Column(Integer)          # 1, 2, 3 ... per inspection
    observation_text = Column(Text, nullable=False)
    system_area = Column(String(200))             # Batch Records, Equipment, Personnel ...
    cfr_citations = Column(JSONB, default=list)   # ["21 CFR 211.188", ...]

    draft_response = Column(Text)
    supporting_evidence = Column(JSONB, default=list)  # doc titles / record refs

    assigned_to = Column(String, ForeignKey("users.id"))
    response_deadline = Column(String(20))        # date string — FDA default 15 biz days
    legal_review_required = Column(Boolean, default=False)

    status = Column(String(20), default="draft")  # draft | under_review | submitted | closed

    created_by = Column(String, ForeignKey("users.id"))
