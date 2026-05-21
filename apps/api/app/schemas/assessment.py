"""Assessment schemas"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AssessmentRunRequest(BaseModel):
    include_references: bool = True
    levels: Optional[list[str]] = None  # If None, run all enabled levels


class FindingResponse(BaseModel):
    id: str
    level: str
    level_name: Optional[str] = None
    severity: str
    category: Optional[str] = None
    title: str
    description: str
    evidence: Optional[str] = None
    location: Optional[str] = None
    regulatory_citation: Optional[str] = None
    citation_type: Optional[str] = None
    agency: Optional[str] = None
    enforcement_match: bool = False
    enforcement_context: Optional[str] = None
    severity_elevated: bool = False
    suggestion_draft: Optional[str] = None
    next_step_text: Optional[str] = None
    status: str
    confidence_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AssessmentResponse(BaseModel):
    id: str
    document_id: str
    status: str
    clyira_score: Optional[float] = None
    score_band: Optional[str] = None
    findings_critical: int = 0
    findings_high: int = 0
    findings_medium: int = 0
    findings_low: int = 0
    findings_info: int = 0
    enforcement_matches: int = 0
    levels_run: Optional[list[str]] = None
    processing_time_seconds: Optional[float] = None
    created_at: datetime
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True


class LevelScoreDetail(BaseModel):
    level: str
    level_name: str
    score: float
    findings_count: int
    weight: float


class AssessmentReportResponse(BaseModel):
    assessment: AssessmentResponse
    findings: list[FindingResponse]
    level_scores: list[LevelScoreDetail]
    document_title: str
    document_category: Optional[str] = None
