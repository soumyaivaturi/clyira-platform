"""Document and DocumentReference models"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"))

    # Identity
    title = Column(String(500), nullable=False)
    document_number = Column(String(100))
    version = Column(String(20), default="1.0")
    effective_date = Column(String(20))

    # 3-Dimension Classification
    function_type = Column(String(100))  # e.g. "Standard Operating Procedure"
    regulatory_category = Column(String(100))  # e.g. "Process Control"
    department_owner = Column(String(100))  # e.g. "Manufacturing"

    # Document Category (V1: SOP, CAPA, ATM)
    document_category = Column(String(50))  # SOP, CAPA, ATM, Deviation, etc.

    # Regulatory frameworks selected at upload time (overrides company-level agencies)
    regulatory_frameworks = Column(JSONB, nullable=True)  # e.g. ["FDA_21CFR211", "ICH_Q10"]

    # DTAP Assignment
    dtap_id = Column(String(50))  # e.g. "DTAP-001" for SOP

    # Content
    file_path = Column(String(500))
    file_type = Column(String(20))  # docx, pdf
    file_size_bytes = Column(Integer)
    extracted_text = Column(Text)
    extracted_sections = Column(JSONB, default=dict)  # structured breakdown

    # Status
    status = Column(String(50), default="uploaded")  # uploaded, processing, ready, assessed, archived

    # Score (latest)
    latest_score = Column(Float)
    latest_assessment_id = Column(String)

    # Relationships
    company = relationship("Company", back_populates="documents")
    assessments = relationship("Assessment", back_populates="document")
    references = relationship("DocumentReference", back_populates="document")


class DocumentReference(Base, TimestampMixin):
    __tablename__ = "document_references"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"))

    # Reference info
    title = Column(String(500))
    description = Column(Text)
    file_path = Column(String(500))
    file_type = Column(String(20))
    extracted_text = Column(Text)

    # Classification
    reference_type = Column(String(100))  # organizational_guideline, internal_standard, checklist, template

    # Relationships
    document = relationship("Document", back_populates="references")
