"""
Shared data types for the assessment engine.
Extracted into a separate module to avoid circular imports between
orchestrator.py and the individual engine modules.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AssessmentContext:
    """All data needed for an assessment run"""
    document_id: str
    company_id: str
    assessment_id: str

    document_text: str
    document_sections: dict = field(default_factory=dict)
    document_category: str = ""

    dtap_profile: Optional[object] = None

    company_agencies: list = field(default_factory=list)
    company_sub_sectors: list = field(default_factory=list)
    regulatory_frameworks: list = field(default_factory=list)  # document-level framework selection

    user_references: list = field(default_factory=list)
    regulatory_context: list = field(default_factory=list)
    enforcement_records: list = field(default_factory=list)
    historical_assessments: list = field(default_factory=list)
    company_documents_metadata: list = field(default_factory=list)


@dataclass
class FindingResult:
    """A single finding produced by the engine"""
    level: str
    severity: str
    category: str
    title: str
    description: str
    evidence: str = ""
    location: str = ""
    regulatory_citation: str = ""
    citation_type: str = ""
    agency: str = ""
    enforcement_match: bool = False
    enforcement_context: str = ""
    severity_elevated: bool = False
    suggestion_draft: str = ""
    next_step_text: str = ""
    confidence_score: float = 0.0
    validated: bool = False
    remediation_priority: int = 0
    # Phase 1 MBR fields
    verification_state: str = ""  # green, red, blue, gray
    field_criticality: str = ""   # critical, high, medium, low
    source_page: Optional[int] = None
    human_verification_required: bool = False
