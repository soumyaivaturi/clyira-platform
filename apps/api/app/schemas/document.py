"""Document schemas"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    title: str
    document_number: Optional[str] = None
    version: str
    document_category: Optional[str] = None
    function_type: Optional[str] = None
    regulatory_category: Optional[str] = None
    department_owner: Optional[str] = None
    dtap_id: Optional[str] = None
    status: str
    latest_score: Optional[float] = None
    file_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int = 1
    per_page: int = 20


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    document_category: str
    dtap_id: Optional[str] = None
    status: str
    message: str


class ReferenceResponse(BaseModel):
    id: str
    document_id: str
    title: str
    description: Optional[str] = None
    reference_type: str
    file_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
