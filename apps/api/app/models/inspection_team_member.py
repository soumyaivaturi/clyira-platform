"""Unified inspection team member — covers all roles across front room, prep room, SMEs, and inspectors."""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionTeamMember(Base, TimestampMixin):
    __tablename__ = "inspection_team_members"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)   # null for external members

    # Identity
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    phone = Column(String(50))
    title = Column(String(255))
    company = Column(String(255))   # for inspectors / consultants

    # Placement & role
    room = Column(String(20), default="prep")
    # front | prep | sme | inspector

    role = Column(String(50))
    # front room: host | scribe | front_runner
    # prep room:  prep_lead | liaison | runner | doc_control | qa_reviewer | tech_reviewer | screener
    # sme/spoc:   sme | spoc
    # external:   inspector | observer | consultant

    secondary_roles = Column(JSONB, default=list)   # person can wear multiple hats
    functional_area = Column(String(100))            # "Manufacturing", "QA", "R&D", etc.

    # SME-specific coaching
    topics = Column(JSONB, default=list)
    approved_talking_points = Column(JSONB, default=list)
    do_not_volunteer = Column(JSONB, default=list)
    known_weak_areas = Column(Text)
    likely_questions = Column(JSONB, default=list)   # [{question, recommended_answer}]

    # Inspector-specific
    fda_district = Column(String(100))
    focus_areas = Column(JSONB, default=list)
    notes_on_style = Column(Text)                    # known inspector tendencies

    # Availability
    availability = Column(String(30), default="available")
    # available | in_audit_room | on_standby | in_prep | unavailable | do_not_call

    notes = Column(Text)
