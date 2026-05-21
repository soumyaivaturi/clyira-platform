"""Readiness schemas"""
from pydantic import BaseModel
from typing import Optional


class DepartmentScore(BaseModel):
    department: str
    score: float
    score_band: str
    weight: float
    document_count: int


class ReadinessDashboardResponse(BaseModel):
    company_id: str
    company_score: float
    score_band: str
    departments: list[DepartmentScore]
    total_documents: int
    trend: Optional[float] = None


class GapItem(BaseModel):
    document_id: str
    title: str
    category: Optional[str] = None
    score: Optional[float] = None
    status: Optional[str] = None


class GapAnalysisResponse(BaseModel):
    company_id: str
    department: Optional[str] = None
    total_documents: int
    assessed_count: int
    gap_count: int
    missing_assessments: list[GapItem]
    poor_scores: list[GapItem]
