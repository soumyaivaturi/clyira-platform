"""Inspection, InspectionRequest, and InspectionLog models"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid

# SLA budget per criticality level (minutes)
SLA_MINUTES = {"critical": 15, "high": 30, "medium": 60, "low": 120}


class Inspection(Base, TimestampMixin):
    __tablename__ = "inspections"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"))

    # Identity
    title = Column(String(500), nullable=False)
    agency = Column(String(50))
    inspection_type = Column(String(50))  # routine, for_cause, pre_approval, surveillance, directed

    # Status
    status = Column(String(50), default="planned")  # planned, active, post_inspection, closed

    # Phase within an active inspection
    current_phase = Column(String(50))  # opening_meeting, facility_tour, document_review, systems_review, closing_meeting

    # Timeline
    start_date = Column(String(20))
    end_date = Column(String(20))
    day_count = Column(Integer, default=0)

    # Scope and agenda
    inspection_scope = Column(JSONB, default=list)  # systems/areas in scope
    agenda = Column(JSONB, default=list)            # [{phase, label, scheduled_time, actual_start, status}]

    # Team
    team_assignments = Column(JSONB, default=dict)  # role -> user_id mapping
    ai_agents_active = Column(JSONB, default=list)  # ["scribe", "prep_manager", ...]

    # Summary (populated on close)
    total_requests = Column(Integer, default=0)
    commitments_made = Column(JSONB, default=list)
    observations_noted = Column(JSONB, default=list)

    # Relationships
    company = relationship("Company", back_populates="inspections")
    requests = relationship("InspectionRequest", back_populates="inspection",
                            foreign_keys="InspectionRequest.inspection_id")
    log_entries = relationship("InspectionLog", back_populates="inspection")


class InspectionRequest(Base, TimestampMixin):
    __tablename__ = "inspection_requests"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)

    # Sequential request number within this inspection (REQ-001, REQ-002, ...)
    request_number = Column(Integer)

    # Content
    request_text = Column(Text, nullable=False)
    criticality = Column(String(20), default="medium")  # critical, high, medium, low
    category = Column(String(50))  # document_request, question, observation, commitment

    # Who / Where
    inspector_name = Column(String(255))
    inspector_department = Column(String(255))
    location = Column(String(500))           # facility area e.g. "Prep Room A · Mfg Floor 2"
    assigned_to = Column(String, ForeignKey("users.id"))
    assigned_to_name = Column(String(255))   # denormalized for display speed
    assigned_to_title = Column(String(255))  # role/title of assignee

    # SLA
    sla_minutes = Column(Integer)            # set at creation from criticality
    due_at = Column(String(50))              # ISO datetime string

    # Status + progress
    status = Column(String(50), default="open")  # open, in_progress, fulfilled, declined
    fulfillment_progress = Column(Integer, default=0)  # 0–100
    response_text = Column(Text)
    response_time_minutes = Column(Integer)

    # AI Support
    ai_suggested_documents = Column(JSONB, default=list)
    ai_talking_points = Column(JSONB, default=list)
    ai_risk_assessment = Column(Text)

    # Relationships
    inspection = relationship("Inspection", back_populates="requests",
                              foreign_keys=[inspection_id])


class InspectionLog(Base, TimestampMixin):
    __tablename__ = "inspection_log"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))

    # Entry
    entry_type = Column(String(50), nullable=False)
    # scribe_note | observation | question | commitment | action_item | deficiency | document_request
    content = Column(Text, nullable=False)
    tags = Column(JSONB, default=list)

    # Context
    timestamp_local = Column(String(30))
    location = Column(String(200))
    participants = Column(JSONB, default=list)

    # Relationships
    inspection = relationship("Inspection", back_populates="log_entries")
