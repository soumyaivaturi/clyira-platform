"""
DTAP-001: Standard Operating Procedure Assessment Profile
Based on the SOP Master Requirements specification.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

SOP_DTAP = DTAPProfile(
    dtap_id="DTAP-001",
    document_category="SOP",
    display_name="Standard Operating Procedure",
    version="1.0",

    # Expected SOP sections
    required_sections=[
        "Purpose",
        "Scope",
        "Responsibilities",
        "Definitions",
        "Procedure",
        "References",
        "Revision History",
    ],
    optional_sections=[
        "Safety Precautions",
        "Equipment and Materials",
        "Acceptance Criteria",
        "Attachments",
        "Training Requirements",
        "Related Documents",
    ],
    section_order_matters=True,

    # Assessment levels
    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                "required_sections_present",
                "section_ordering",
                "header_format_consistency",
                "page_numbering",
                "table_of_contents",
                "document_number_format",
                "version_control_block",
                "approval_signatures",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "effective_date_present",
                "review_date_present",
                "supersedes_reference",
                "change_control_entries",
                "author_reviewer_approver",
                "distribution_list",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.5,
            checks=[
                "clarity_and_specificity",
                "actionable_instructions",
                "ambiguity_detection",
                "completeness_of_procedure",
                "gap_in_decision_points",
                "missing_contingency_handling",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "alcoa_attributable",
                "alcoa_legible",
                "alcoa_contemporaneous",
                "alcoa_original",
                "alcoa_accurate",
                "data_recording_instructions",
                "form_attachment_references",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.0,
            checks=[
                "critical_parameters_identified",
                "acceptance_criteria_defined",
                "measurement_units_specified",
                "statistical_methods_referenced",
            ],
        ),
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.3,
            checks=[
                "cross_reference_consistency",
                "form_sop_alignment",
                "referenced_docs_exist",
                "terminology_consistency",
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "review_cycle_compliance",
                "training_requirements_defined",
                "obsolescence_handling",
                "periodic_review_trigger",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.5,
            checks=[
                "regulatory_citation_coverage",
                "cfr_alignment",
                "guidance_compliance",
                "gap_vs_current_regulations",
            ],
            required_context=["document_text", "regulatory_corpus", "company_agencies"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.4,
            checks=[
                "enforcement_pattern_match",
                "warning_letter_similarity",
                "483_observation_alignment",
                "severity_elevation_check",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),
        "L10": LevelConfig(
            enabled=True,
            engine="llm",
            weight=0.7,
            checks=[
                "score_trend_analysis",
                "recurring_finding_detection",
                "improvement_trajectory",
            ],
            required_context=["historical_assessments"],
        ),
        "L11": LevelConfig(
            enabled=False,  # Only for submission-related docs
            engine="hybrid",
            weight=1.0,
            checks=[
                "submission_format_compliance",
                "ectd_structure",
                "module_completeness",
            ],
        ),
    },

    # Scoring weights per level
    score_weights={
        "L1": 0.08,
        "L2": 0.07,
        "L3": 0.18,
        "L4": 0.12,
        "L5": 0.10,
        "L6": 0.12,
        "L7": 0.06,
        "L8": 0.15,
        "L9": 0.08,
        "L10": 0.04,
    },

    passing_threshold=70.0,

    # Sector overlays
    sector_overlays={
        "SS-B1": {  # Biologics - Monoclonal Antibodies
            "additional_required_sections": ["Biosafety Considerations"],
            "L5_extra_checks": ["cell_line_parameters", "viral_clearance_steps"],
        },
        "SS-S1": {  # Sterile Injectable
            "additional_required_sections": ["Aseptic Technique", "Environmental Controls"],
            "L4_extra_checks": ["media_fill_references", "hold_time_specifications"],
        },
    },
)
