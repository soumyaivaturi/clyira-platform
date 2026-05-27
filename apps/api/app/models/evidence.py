"""Evidence Fabric — Layer 1 (Universal Intake) + Layer 2 (Evidence Object Store)"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class EvidenceImport(Base, TimestampMixin):
    """A single CSV/Excel file ingested by the Evidence Fabric."""
    __tablename__ = "evidence_imports"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    uploaded_by = Column(String, ForeignKey("users.id"))

    filename = Column(String(500), nullable=False)
    source_system = Column(String(100))     # qms, lims, mes, cmms, eln, erp, manual
    record_count = Column(Integer, default=0)
    status = Column(String(30), default="processing")  # processing | ready | error
    error_message = Column(Text)

    # Raw column headers detected in the file
    detected_columns = Column(JSONB, default=list)

    # Column-to-field mapping set by the user (e.g., {"Date": "event_date", "Batch": "entity_id"})
    column_mapping = Column(JSONB, default=dict)

    # Entity type this dataset represents (deviation, oos, training, equipment, material, pm)
    entity_type = Column(String(50))

    # Storage path
    file_path = Column(String(500))

    # Full parsed row set stored at upload time so /map can re-ingest without a second upload
    raw_rows = Column(JSONB, default=list)


class EvidenceObject(Base, TimestampMixin):
    """A single normalized evidence record extracted from an EvidenceImport."""
    __tablename__ = "evidence_objects"

    id = Column(String, primary_key=True, default=generate_uuid)
    import_id = Column(String, ForeignKey("evidence_imports.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)

    # Entity classification (Layer 3 — Regulated Entity Registry)
    entity_type = Column(String(50))        # equipment, personnel, material, method, room, utility, system, sample
    entity_id = Column(String(255))         # canonical identifier (equipment ID, analyst name, batch number, etc.)
    entity_name = Column(String(500))

    # Quality Signal (Layer 4)
    signal_type = Column(String(50))        # deviation, oos, pm_overdue, training_gap, em_excursion, change_control
    event_date = Column(String(30))
    severity = Column(String(20))           # critical, major, minor, informational

    # Raw + structured payload
    raw_row = Column(JSONB, default=dict)   # original CSV row as-is
    normalized = Column(JSONB, default=dict) # mapped fields

    # Cross-reference metadata
    linked_document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    cfr_citations = Column(JSONB, default=list)
    tags = Column(JSONB, default=list)
