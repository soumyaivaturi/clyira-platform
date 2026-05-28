"""
ProductProfile — per-product classification defaults + MBR template memory.

Stores the Layer 0 classification defaults for a product line so users don't
re-enter them on every dossier. Also stores the extracted required-field list
and acceptance criteria from an uploaded blank MBR template.
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class ProductProfile(Base, TimestampMixin):
    __tablename__ = "product_profiles"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)

    # Identity
    profile_name = Column(String(255), nullable=False)   # e.g. "Amoxicillin 500mg Capsules"
    product_code = Column(String(100), nullable=True)
    product_name = Column(String(255), nullable=True)
    dosage_form = Column(String(100), nullable=True)
    manufacturing_site = Column(String(255), nullable=True)

    # Layer 0 classification defaults
    record_family = Column(String(50), default="pharma_bpr")
    product_type = Column(String(50), default="small_molecule")
    is_sterile = Column(Boolean, default=False)
    manufacturing_context = Column(String(50), default="internal")
    batch_purpose = Column(String(50), default="commercial")
    target_markets = Column(JSONB, default=list)

    # MBR template memory — populated via /analyze-template endpoint
    template_document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    template_required_fields = Column(JSONB, nullable=True)   # list[str]
    template_acceptance_criteria = Column(JSONB, nullable=True)  # list[{field_context, spec}]
    template_section_count = Column(String(10), nullable=True)
    template_analyzed_at = Column(String, nullable=True)

    # CPP / spec documents that inform acceptance criteria
    spec_document_ids = Column(JSONB, default=list)  # list of document IDs

    active = Column(Boolean, default=True)

    # Relationships
    company = relationship("Company")
    template_document = relationship("Document", foreign_keys=[template_document_id])
