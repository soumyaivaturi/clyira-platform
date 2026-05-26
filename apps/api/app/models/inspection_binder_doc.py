"""Inspection binder — pre-staged document checklist for the audit room."""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionBinderDoc(Base, TimestampMixin):
    __tablename__ = "inspection_binder_docs"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)

    category = Column(String(50), default="other")
    # company_profile|org_chart|sop_index|site_master_file|capa_summary|deviation_log
    # training_records|batch_records|validation_summary|equipment_list|calibration_log
    # environmental_monitoring|supplier_qualification|change_control|complaint_log|other

    title = Column(String(500), nullable=False)
    filename = Column(String(500))
    version = Column(String(50))
    document_date = Column(String(20))

    status = Column(String(20), default="missing")
    # missing | staged | ready | delivered | withdrawn

    required = Column(Boolean, default=True)
    notes = Column(Text)

    linked_request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)

    staged_by_name = Column(String(255))
    staged_at = Column(String(50))
    delivered_at = Column(String(50))
    delivered_to = Column(String(255))
