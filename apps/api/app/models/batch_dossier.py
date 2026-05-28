"""
Batch & Lot Record Review Module — Data Models
Phase 2 MVP: BatchDossier, BatchDossierDocument, EvidencePackageTemplate, FeedbackCorrection
"""
from sqlalchemy import Column, String, Text, Integer, Float, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class BatchDossier(Base, TimestampMixin):
    """
    A lot-level review package linking an executed production record to all
    supporting quality evidence. This is the core unit of the MBR module.
    """
    __tablename__ = "batch_dossiers"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)

    # Lot identification
    lot_number = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    product_code = Column(String(100), nullable=True)
    dosage_form = Column(String(100), nullable=True)
    batch_size = Column(String(100), nullable=True)
    manufacturing_site = Column(String(255), nullable=True)
    manufacturing_date = Column(String(50), nullable=True)
    target_release_date = Column(String(50), nullable=True)

    # Layer 0 Classification
    record_family = Column(String(50), default="pharma_bpr")
    # pharma_bpr, api_batch, biologics_batch, sterile_batch, device_dhr,
    # supplement_bpr, cell_therapy, blood_plasma, cdmo_package
    product_type = Column(String(50), default="small_molecule")
    # small_molecule, biologic, vaccine, api, combination, supplement, device, cell_therapy, gene_therapy
    is_sterile = Column(Boolean, default=False)
    manufacturing_context = Column(String(20), default="internal")  # internal, cdmo_received
    batch_purpose = Column(String(30), default="commercial")
    # commercial, validation, exhibit, stability, tech_transfer, clinical, scale_up
    target_markets = Column(JSONB, default=list)  # ["FDA", "EMA", "PMDA", ...]

    # Status and readiness
    status = Column(String(30), default="draft")
    # draft, under_review, pending_disposition, released, conditionally_released,
    # on_hold, rejected, reopened
    readiness_status = Column(String(20), nullable=True)  # ready, conditional, not_ready, hold
    readiness_score = Column(Float, nullable=True)
    readiness_band = Column(String(30), nullable=True)

    # Human disposition decision
    disposition_decision = Column(String(30), nullable=True)  # release, conditional_release, hold, reject
    disposition_rationale = Column(Text, nullable=True)
    disposition_divergence = Column(Boolean, default=False)
    conditional_release_conditions = Column(JSONB, nullable=True)

    # Release gates (all must pass for "Ready" status)
    gate_evidence_complete = Column(Boolean, default=False)
    gate_open_deviations = Column(Boolean, default=True)    # True = gate blocked (open deviations exist)
    gate_open_capas = Column(Boolean, default=True)
    gate_qc_complete = Column(Boolean, default=False)
    gate_data_integrity = Column(Boolean, default=True)     # True = data integrity concern exists
    gate_all_findings_addressed = Column(Boolean, default=False)
    gate_gray_findings_resolved = Column(Boolean, default=False)

    # Review workflow
    shadow_mode = Column(Boolean, default=False)
    review_stage = Column(String(30), nullable=True)  # cdmo_internal, sponsor_review, complete

    # Audit
    released_by = Column(String, ForeignKey("users.id"), nullable=True)
    released_at = Column(String, nullable=True)

    # Relationships
    documents = relationship("BatchDossierDocument", back_populates="dossier", cascade="all, delete-orphan")
    company = relationship("Company")
    creator = relationship("User", foreign_keys=[created_by])


class BatchDossierDocument(Base, TimestampMixin):
    """
    Join table linking a document to a batch dossier with role metadata.
    Each dossier can contain multiple documents in different roles.
    """
    __tablename__ = "batch_dossier_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    dossier_id = Column(String, ForeignKey("batch_dossiers.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)

    role = Column(String(50), default="other")
    # primary_bpr, deviation, capa, qc_result, coa, environmental_monitoring,
    # equipment_log, reprocessing_record, sterilization_record, filter_integrity,
    # packaging_record, labeling_record, other

    sequence_order = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    added_by = Column(String, ForeignKey("users.id"), nullable=False)

    # Relationships
    dossier = relationship("BatchDossier", back_populates="documents")
    document = relationship("Document")


class EvidencePackageTemplate(Base, TimestampMixin):
    """
    Defines what documents are expected in a dossier for a given record family
    and product type. Used by the evidence completeness gate.
    """
    __tablename__ = "evidence_package_templates"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    record_family = Column(String(50), nullable=False)
    product_type = Column(String(50), nullable=True)
    is_sterile = Column(Boolean, nullable=True)
    required_document_roles = Column(JSONB, default=list)
    optional_document_roles = Column(JSONB, default=list)
    sterile_additional_roles = Column(JSONB, nullable=True)
    description = Column(Text, nullable=True)


class FeedbackCorrection(Base, TimestampMixin):
    """
    Stores reviewer corrections to AI-extracted or AI-assessed values.
    Tenant-scoped training signal for continuous improvement.
    """
    __tablename__ = "feedback_corrections"

    id = Column(String, primary_key=True, default=generate_uuid)
    finding_id = Column(String, ForeignKey("findings.id"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    corrected_by = Column(String, ForeignKey("users.id"), nullable=False)

    field_name = Column(String(200), nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=False)
    source_page = Column(Integer, nullable=True)
    bounding_box = Column(JSONB, nullable=True)
    extraction_confidence = Column(Float, nullable=True)
    recognition_method = Column(String(30), nullable=True)  # digital, ocr, icr, iwr, manual
    field_criticality = Column(String(10), nullable=True)
    correction_rationale = Column(Text, nullable=True)
