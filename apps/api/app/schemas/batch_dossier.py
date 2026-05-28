"""Pydantic schemas for the Batch & Lot Record Review module."""
from typing import Optional
from pydantic import BaseModel


class BatchDossierCreate(BaseModel):
    lot_number: str
    product_name: str
    product_code: Optional[str] = None
    dosage_form: Optional[str] = None
    batch_size: Optional[str] = None
    manufacturing_site: Optional[str] = None
    manufacturing_date: Optional[str] = None
    target_release_date: Optional[str] = None
    # Layer 0 classification
    record_family: str = "pharma_bpr"
    product_type: str = "small_molecule"
    is_sterile: bool = False
    manufacturing_context: str = "internal"
    batch_purpose: str = "commercial"
    target_markets: list[str] = []
    shadow_mode: bool = False


class BatchDossierUpdate(BaseModel):
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    dosage_form: Optional[str] = None
    batch_size: Optional[str] = None
    manufacturing_site: Optional[str] = None
    manufacturing_date: Optional[str] = None
    target_release_date: Optional[str] = None
    record_family: Optional[str] = None
    product_type: Optional[str] = None
    is_sterile: Optional[bool] = None
    manufacturing_context: Optional[str] = None
    batch_purpose: Optional[str] = None
    target_markets: Optional[list[str]] = None
    status: Optional[str] = None
    shadow_mode: Optional[bool] = None


class DispositionDecisionCreate(BaseModel):
    decision: str  # release, conditional_release, hold, reject
    rationale: str
    conditional_conditions: Optional[list[str]] = None


class BatchDossierDocumentAdd(BaseModel):
    document_id: str
    role: str = "other"
    sequence_order: Optional[int] = None
    notes: Optional[str] = None


class FeedbackCorrectionCreate(BaseModel):
    finding_id: str
    document_id: str
    field_name: str
    original_value: Optional[str] = None
    corrected_value: str
    source_page: Optional[int] = None
    field_criticality: Optional[str] = None
    correction_rationale: Optional[str] = None
