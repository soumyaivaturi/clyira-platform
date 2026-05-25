"""Regulatory Corpus and Enforcement Record models"""
from sqlalchemy import Column, String, Text, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class RegulatoryCorpus(Base, TimestampMixin):
    __tablename__ = "regulatory_corpus"

    id = Column(String, primary_key=True, default=generate_uuid)

    # Classification
    hierarchy_level = Column(Integer, nullable=False)  # 0-6 (L0 Internal to L6 Enforcement)
    agency = Column(String(50), nullable=False)  # FDA, EMA, MHRA, TGA, etc.
    document_type = Column(String(100))  # guidance, regulation, statute, standard

    # Content
    title = Column(String(500), nullable=False)
    citation_reference = Column(String(200))  # e.g. "21 CFR 211.100(a)"
    section = Column(String(200))
    content = Column(Text, nullable=False)
    effective_date = Column(String(20))

    # Applicability
    sub_sectors = Column(JSONB, default=list)  # Which sub-sectors this applies to
    document_categories = Column(JSONB, default=list)  # Which doc types it applies to
    departments = Column(JSONB, default=list)  # Which departments

    # Embedding stored as JSONB array (migrate to pgvector when available on host)
    embedding = Column(JSONB, nullable=True)

    # Status
    is_current = Column(Boolean, default=True)
    superseded_by = Column(String)


class FailureMode(Base, TimestampMixin):
    __tablename__ = "failure_modes"

    id = Column(String(20), primary_key=True)  # FM-001, FM-002, …

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    frequency = Column(Integer, default=0)
    affected_companies_count = Column(Integer, default=0)

    primary_cfr_citations = Column(JSONB, default=list)
    observed_cfr_sections = Column(JSONB, default=list)
    keywords = Column(JSONB, default=list)

    severity_range = Column(JSONB, default=list)
    doc_categories = Column(JSONB, default=list)
    sub_sectors = Column(JSONB, default=list)
    root_cause_categories = Column(JSONB, default=list)
    evidence_indicators = Column(JSONB, default=list)

    example_observation_ids = Column(JSONB, default=list)
    observation_years = Column(JSONB, default=list)
    offices = Column(JSONB, default=dict)

    agency = Column(String(50), default="FDA")
    is_current = Column(Boolean, default=True)


class EnforcementRecord(Base, TimestampMixin):
    __tablename__ = "enforcement_records"

    id = Column(String, primary_key=True, default=generate_uuid)

    # Source
    agency = Column(String(50), nullable=False)
    record_type = Column(String(50), nullable=False)  # warning_letter, 483, consent_decree, recall
    reference_number = Column(String(100))  # e.g. "WL-2025-0042"
    issue_date = Column(String(20))
    company_cited = Column(String(255))

    # Classification
    sub_sectors = Column(JSONB, default=list)  # Which sub-sectors affected
    observation_categories = Column(JSONB, default=list)  # Mapped to our category taxonomy
    cfr_citations = Column(JSONB, default=list)  # Referenced regulations

    # Content
    title = Column(String(500))
    summary = Column(Text)
    observations = Column(JSONB, default=list)  # Structured observation list
    outcome = Column(String(100))  # resolved, consent_decree, seizure, injunction

    # Intelligence
    pattern_tags = Column(JSONB, default=list)  # Derived patterns
    severity_indicator = Column(String(20))  # How severe the enforcement action was
    trending = Column(Boolean, default=False)  # Is this a trending pattern?
    trend_velocity = Column(Float)  # Rate of increase in similar findings

    # Embedding stored as JSONB array (migrate to pgvector when available on host)
    embedding = Column(JSONB, nullable=True)
