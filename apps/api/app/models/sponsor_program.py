"""
SponsorProgram — CDMO multi-sponsor tenancy model.

A single CDMO account can manufacture for multiple sponsors. Each SponsorProgram
defines the sponsor-specific DTAP overlay, CPP/IPC ranges, evidence package template,
and review workflow for that sponsor's lots.
"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class SponsorProgram(Base, TimestampMixin):
    __tablename__ = "sponsor_programs"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    sponsor_name = Column(String(255), nullable=False)
    sponsor_code = Column(String(50), nullable=True)

    # Sponsor-specific DTAP additions (extra checks beyond CDMO's base DTAP)
    dtap_overlay = Column(JSONB, nullable=True)

    # Sponsor-defined CPP / IPC ranges (override CDMO defaults)
    cpp_ipc_ranges = Column(JSONB, nullable=True)

    # Quality agreement reference
    quality_agreement_reference = Column(String(255), nullable=True)

    # Evidence template — which documents the sponsor expects in a lot package
    evidence_template_id = Column(String, ForeignKey("evidence_package_templates.id"), nullable=True)

    active = Column(Boolean, default=True, nullable=False)

    # Relationships
    dossiers = relationship("BatchDossier", back_populates="sponsor_program")
