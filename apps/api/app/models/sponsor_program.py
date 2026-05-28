"""
SponsorProgram — CDMO multi-sponsor tenancy model.

A single CDMO account can manufacture for multiple sponsors. Each SponsorProgram
defines the sponsor-specific DTAP overlay, CPP/IPC ranges, evidence package template,
and review workflow for that sponsor's lots.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class SponsorProgram(Base):
    __tablename__ = "sponsor_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    sponsor_name = Column(String(255), nullable=False)
    sponsor_code = Column(String(50), nullable=True)

    # Sponsor-specific DTAP additions (extra checks beyond CDMO's base DTAP)
    dtap_overlay = Column(JSONB, nullable=True)

    # Sponsor-defined CPP / IPC ranges (override CDMO defaults)
    cpp_ipc_ranges = Column(JSONB, nullable=True)

    # Quality agreement reference
    quality_agreement_reference = Column(String(255), nullable=True)

    # Evidence template — which documents the sponsor expects in a lot package
    evidence_template_id = Column(UUID(as_uuid=True), ForeignKey("evidence_package_templates.id"), nullable=True)

    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    dossiers = relationship("BatchDossier", back_populates="sponsor_program", lazy="dynamic")
