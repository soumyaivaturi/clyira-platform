"""InspectionSME — subject-matter expert prep and availability tracking"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionSME(Base, TimestampMixin):
    __tablename__ = "inspection_smes"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)

    # Identity
    name = Column(String(255), nullable=False)
    title = Column(String(255))
    department = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))

    # Room assignment
    room = Column(String(50), default="prep")    # front | back | prep | unavailable

    # Availability
    availability = Column(String(50), default="available")
    # available | in_audit_room | on_standby | in_prep | unavailable | do_not_call

    # Topic ownership
    topics = Column(JSONB, default=list)         # ["Batch Records", "CAPA", "Sterility Assurance"]
    backup_for = Column(String(255))             # name of person this SME backs up

    # Prep status
    prep_status = Column(String(50), default="not_started")  # not_started | in_progress | ready | qa_cleared
    qa_cleared = Column(Boolean, default=False)
    qa_cleared_by = Column(String, ForeignKey("users.id"), nullable=True)
    qa_cleared_at = Column(String(50))

    # Coaching content
    approved_talking_points = Column(JSONB, default=list)    # list of strings
    do_not_volunteer = Column(JSONB, default=list)           # topics SME should not raise
    do_not_speculate = Column(JSONB, default=list)           # areas requiring verification first
    escalation_triggers = Column(JSONB, default=list)        # "if asked about X, escalate to QA"
    likely_questions = Column(JSONB, default=list)           # [{question, recommended_answer}]
    relevant_documents = Column(JSONB, default=list)         # document titles/ids
    known_weak_areas = Column(Text)                          # internal notes on gaps

    # Call log
    call_log = Column(JSONB, default=list)   # [{called_at, called_by, reason, notes}]

    # Notes
    notes = Column(Text)
