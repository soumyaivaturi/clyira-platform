"""Assessment and Finding models"""
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Assessment(Base, TimestampMixin):
    __tablename__ = "assessments"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    triggered_by = Column(String, ForeignKey("users.id"))

    # Status
    status = Column(String(50), default="queued")  # queued, running, completed, failed
    started_at = Column(String)
    completed_at = Column(String)

    # Configuration
    dtap_id = Column(String(50))
    levels_run = Column(JSONB, default=list)  # e.g. ["L1","L2","L3",...]
    include_references = Column(Boolean, default=False)
    agencies_assessed = Column(JSONB, default=list)

    # Results
    clyira_score = Column(Float)
    score_band = Column(String(20))  # Excellent, Good, Moderate, Poor, Critical

    # Finding counts
    findings_critical = Column(Integer, default=0)
    findings_high = Column(Integer, default=0)
    findings_medium = Column(Integer, default=0)
    findings_low = Column(Integer, default=0)
    findings_info = Column(Integer, default=0)

    # Enforcement
    enforcement_matches = Column(Integer, default=0)
    enforcement_details = Column(JSONB, default=list)

    # Metadata
    processing_time_seconds = Column(Float)
    tokens_used = Column(Integer)
    model_version = Column(String(50))
    error_detail = Column(Text)  # Stores traceback on failure for debugging

    # Relationships
    document = relationship("Document", back_populates="assessments")
    company = relationship("Company", back_populates="assessments")
    findings = relationship("Finding", back_populates="assessment")


class Finding(Base, TimestampMixin):
    __tablename__ = "findings"

    id = Column(String, primary_key=True, default=generate_uuid)
    assessment_id = Column(String, ForeignKey("assessments.id"), nullable=False)

    # Classification
    level = Column(String(10), nullable=False)  # L1, L2, ..., L11
    level_name = Column(String(100))  # e.g. "Structural Integrity"
    severity = Column(String(20), nullable=False)  # critical, high, medium, low, info
    category = Column(String(100))  # e.g. "missing_section", "citation_gap"

    # Content
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text)  # What was found / what triggered
    location = Column(String(200))  # Section reference in document

    # Regulatory Basis
    regulatory_citation = Column(Text)  # The specific regulation
    citation_type = Column(String(50))  # direct, traceability, substantive
    agency = Column(String(50))  # Which agency's rule

    # Enforcement Context
    enforcement_match = Column(Boolean, default=False)
    enforcement_record_id = Column(String)
    enforcement_context = Column(Text)  # "Similar finding cited in WL-2025-XXX"
    severity_elevated = Column(Boolean, default=False)  # Was severity bumped due to enforcement

    # Remediation
    suggestion_draft = Column(Text)  # AI-generated fix suggestion
    next_step_text = Column(Text)  # Recommended action
    remediation_priority = Column(Integer)  # 1=immediate, 2=short-term, 3=medium-term

    # Status workflow
    status = Column(String(50), default="open")  # open, acknowledged, in_progress, resolved, disputed
    response_text = Column(Text)  # User's response to finding
    resolved_at = Column(String)

    # Anti-hallucination gate
    validated = Column(Boolean, default=False)  # Passed verification check
    confidence_score = Column(Float)  # Model confidence in finding

    # Relationships
    assessment = relationship("Assessment", back_populates="findings")
