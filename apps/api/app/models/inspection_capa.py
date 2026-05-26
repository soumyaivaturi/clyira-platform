"""InspectionCAPA — post-inspection CAPA / action items"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionCAPA(Base, TimestampMixin):
    __tablename__ = "inspection_capas"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"))

    # Type
    action_type = Column(String(50), default="capa")
    # capa | correction | preventive | training | sop_revision | validation | supplier | data_integrity | other

    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Linkage
    linked_observation_id = Column(String, ForeignKey("inspection_observations.id"), nullable=True)
    linked_request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)
    linked_commitment_id = Column(String, ForeignKey("inspection_commitments.id"), nullable=True)
    linked_potential_finding_id = Column(String, ForeignKey("inspection_potential_findings.id"), nullable=True)

    # Assignment
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    owner_name = Column(String(255))
    department = Column(String(100))

    # Timeline
    due_date = Column(String(20))
    completed_at = Column(String(50))
    verified_at = Column(String(50))

    # Status
    status = Column(String(50), default="open")
    # open | in_progress | qa_review | completed | verified | closed | overdue

    criticality = Column(String(20), default="medium")  # low | medium | high | critical

    # Completion
    completion_notes = Column(Text)
    effectiveness_check_required = Column(Boolean, default=False)
    effectiveness_check_due = Column(String(20))
    effectiveness_check_notes = Column(Text)
    management_review_required = Column(Boolean, default=False)

    # QMS export
    qms_exported = Column(Boolean, default=False)
    qms_record_id = Column(String(255))
    lesson_learned = Column(Text)
