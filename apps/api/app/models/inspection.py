"""Inspection, InspectionRequest, and InspectionLog models"""
from sqlalchemy import Boolean, Column, String, Text, Integer, ForeignKey
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

    # Section 1 — extended setup
    sector = Column(String(100))         # small_molecule | biologics | medical_device | cdmo | etc.
    products_in_scope = Column(JSONB, default=list)
    departments_in_scope = Column(JSONB, default=list)
    regulatory_frameworks = Column(JSONB, default=list)  # ["21_cfr_211", "eu_gmp", "ich_q10", ...]
    site_name = Column(String(255))
    mode = Column(String(30), default="onsite")   # onsite | remote | hybrid
    default_sla_settings = Column(JSONB, default=dict)  # {critical: 15, high: 30, medium: 60, low: 120}

    # Scope and agenda
    inspection_scope = Column(JSONB, default=list)  # systems/areas in scope
    agenda = Column(JSONB, default=list)            # [{phase, label, scheduled_time, actual_start, status}]

    # Team roles (Section 3)
    team_assignments = Column(JSONB, default=dict)
    # {host: user_id, qa_lead: user_id, prep_room_manager: user_id, scribe: user_id, runner: user_id, ...}
    ai_agents_active = Column(JSONB, default=list)  # ["scribe", "prep_manager", ...]

    # Command center live metrics cache (Section 2)
    avg_response_time_minutes = Column(Integer)
    last_daily_brief = Column(Text)
    last_daily_brief_at = Column(String(50))

    # Summary (populated on close)
    total_requests = Column(Integer, default=0)
    commitments_made = Column(JSONB, default=list)
    observations_noted = Column(JSONB, default=list)

    # Inspector-safe mode flag (hides internal-only data)
    inspector_safe_mode = Column(Boolean, default=False)

    # Post-inspection (Section 18)
    outcome = Column(String(50))           # no_action | warning_letter_risk | 483_issued | eir_pending | closed_satisfactorily
    final_483_count = Column(Integer, default=0)
    post_inspection_notes = Column(Text)
    lessons_learned = Column(JSONB, default=list)
    sign_offs = Column(JSONB, default=dict)  # {qa_lead: bool, site_director: bool, reg_affairs: bool, legal: bool}
    closed_at = Column(String(50))          # ISO timestamp when inspection moved to post_inspection

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

    # Extended classification (Section 4)
    request_type = Column(String(50))
    # document_request | data_request | interview | facility_tour | demonstration
    # system_access | clarification | follow_up | commitment | observation_response
    request_category = Column(String(100))
    # batch_record | sop | deviation | capa | change_control | oos | lab_investigation
    # training | validation | equipment | calibration | maintenance | cleaning
    # environmental_monitoring | sterility | stability | supplier | complaint | data_integrity
    # computer_system | method_validation | specification | coa | raw_data | risk_management
    regulatory_risk = Column(String(30), default="low")  # low | medium | high | potential_observation
    related_lot = Column(String(255))
    related_product = Column(String(255))

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

    # Status + progress — extended lifecycle
    status = Column(String(50), default="open")
    # open | triage | assigned | in_progress | evidence_gathering | qa_review
    # approved | released | inspector_review | fulfilled | closed | declined | withdrawn
    fulfillment_progress = Column(Integer, default=0)  # 0–100
    response_text = Column(Text)
    response_time_minutes = Column(Integer)

    # QA Gate fields
    qa_reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    qa_reviewed_at = Column(String(50))
    qa_notes = Column(Text)
    released_by = Column(String, ForeignKey("users.id"), nullable=True)
    released_at = Column(String(50))

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
