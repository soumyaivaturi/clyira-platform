"""InspectionEvidencePackage — documents assembled for a request, subject to QA gate"""
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionEvidencePackage(Base, TimestampMixin):
    __tablename__ = "inspection_evidence_packages"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)
    request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)

    title = Column(String(500), nullable=False)
    description = Column(Text)

    # Status lifecycle: draft → staged → qa_review → approved → released | returned | withdrawn
    status = Column(String(50), default="draft")

    # Documents in this package (denormalized for speed)
    # [{id, filename, document_id, version, approval_status, flags: {internal_notes, redaction_required, confidential, draft_warning}}]
    documents = Column(JSONB, default=list)

    # Risk & completeness
    package_risk = Column(String(20), default="low")   # low | medium | high | critical
    completeness_status = Column(String(50), default="incomplete")  # incomplete | complete | reviewed

    # Ownership
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    owner_name = Column(String(255))

    # QA Gate
    qa_approver_id = Column(String, ForeignKey("users.id"), nullable=True)
    qa_approver_name = Column(String(255))
    qa_approved_at = Column(String(50))
    qa_notes = Column(Text)
    qa_checks = Column(JSONB, default=dict)   # {relevance, version, approval, alignment, no_extra, no_internal, no_draft, redaction}

    # Release
    released_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    released_by_name = Column(String(255))
    released_at = Column(String(50))
    release_notes = Column(Text)

    # Flags
    legal_review_required = Column(Boolean, default=False)
    dual_approval_required = Column(Boolean, default=False)
    second_approver_id = Column(String, ForeignKey("users.id"), nullable=True)
    second_approved_at = Column(String(50))
