"""InspectionPotentialFinding — strategic threat tracker during live inspections"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionPotentialFinding(Base, TimestampMixin):
    __tablename__ = "inspection_potential_findings"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"))

    # What is this finding
    title = Column(String(500), nullable=False)
    inspector_framing = Column(Text)      # how inspector would write it in a 483
    system_area = Column(String(200))     # e.g. "Sterility Assurance", "Batch Records"
    cfr_citations = Column(JSONB, default=list)  # ["21 CFR 211.68", ...]

    # Confidence and status
    confidence = Column(String(20), default="medium")  # low | medium | high | certain
    status = Column(String(50), default="tracking")    # tracking | responded | resolved | escalated_to_483

    # Defense
    defense_summary = Column(Text)                    # internal defense notes
    linked_request_ids = Column(JSONB, default=list)  # InspectionRequest ids driving this finding
    linked_document_ids = Column(JSONB, default=list) # Document ids that support the defense

    # QA Gate
    qa_reviewed = Column(Boolean, default=False)
    qa_reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    qa_reviewed_at = Column(String(50), nullable=True)

    # Provenance
    ai_generated = Column(Boolean, default=False)     # surfaced by AI scan vs manual entry
    source = Column(String(50), default="manual")     # manual | ai_scan | converted_from_request
