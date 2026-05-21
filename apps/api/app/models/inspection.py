"""Inspection, InspectionRequest, and InspectionLog models"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Inspection(Base, TimestampMixin):
    __tablename__ = "inspections"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"))

    # Identity
    title = Column(String(500), nullable=False)
    agency = Column(String(50))
    inspection_type = Column(String(50))  # routine, for_cause, pre_approval, surveillance

    # Status
    status = Column(String(50), default="planned")  # planned, active, post_inspection, closed

    # Timeline
    start_date = Column(String(20))
    end_date = Column(String(20))
    day_count = Column(Integer, default=0)

    # Team
    team_assignments = Column(JSONB, default=dict)  # role -> user_id mapping
    ai_agents_active = Column(JSONB, default=list)  # ["scribe", "prep_manager", ...]

    # Summary (populated on close)
    total_requests = Column(Integer, default=0)
    commitments_made = Column(JSONB, default=list)
    observations_noted = Column(JSONB, default=list)

    # Relationships
    company = relationship("Company", back_populates="inspections")
    requests = relationship("InspectionRequest", back_populates="inspection")
    log_entries = relationship("InspectionLog", back_populates="inspection")


class InspectionRequest(Base, TimestampMixin):
    __tablename__ = "inspection_requests"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)

    # Content
    request_text = Column(Text, nullable=False)
    criticality = Column(String(20), default="medium")  # critical, high, medium, low
    category = Column(String(50))  # document_request, question, observation, commitment

    # Status
    status = Column(String(50), default="open")  # open, in_progress, responded, closed
    assigned_to = Column(String, ForeignKey("users.id"))
    response_text = Column(Text)
    response_time_minutes = Column(Integer)

    # AI Support
    ai_suggested_documents = Column(JSONB, default=list)
    ai_talking_points = Column(JSONB, default=list)
    ai_risk_assessment = Column(Text)

    # Relationships
    inspection = relationship("Inspection", back_populates="requests")


class InspectionLog(Base, TimestampMixin):
    __tablename__ = "inspection_log"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))

    # Entry
    entry_type = Column(String(50), nullable=False)  # scribe_note, observation, question, commitment, action_item
    content = Column(Text, nullable=False)
    tags = Column(JSONB, default=list)

    # Context
    timestamp_local = Column(String(30))  # Local time of entry
    location = Column(String(200))  # Where in facility
    participants = Column(JSONB, default=list)  # Who was present

    # Relationships
    inspection = relationship("Inspection", back_populates="log_entries")
