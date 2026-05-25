"""
DTAP-006: Validation Protocol/Report Assessment Profile
Covers IQ/OQ/PQ, process validation, cleaning validation, computer system validation.
Grounded in 21 CFR 211.68, 21 CFR 820.70, FDA Process Validation Guidance 2011, EU GMP Annex 11/15.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

VALIDATION_DTAP = DTAPProfile(
    dtap_id="DTAP-006",
    document_category="Validation",
    display_name="Validation Protocol / Report",
    version="1.0",

    required_sections=[
        "Purpose / Objective",
        "Scope",
        "Responsibilities",
        "System / Equipment Description",
        "Acceptance Criteria",
        "Test / Execution Procedure",
        "Results",
        "Conclusion and Summary",
        "Deviations / Discrepancies",
        "Approval Signatures",
    ],
    optional_sections=[
        "Risk Assessment",
        "References",
        "Attachments / Raw Data",
        "Requalification Schedule",
        "Change Control References",
        "Validation Master Plan Reference",
    ],
    section_order_matters=False,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "required_sections_present",
                "validation_type_declared",
                "protocol_report_distinction",
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
                "qa_independence",
                "author_reviewer_approver",
                "change_control_entries",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.8,
            checks=[
                "acceptance_criteria_prespecified",
                "test_step_completeness",
                "worst_case_rationale",
                "statistical_adequacy",
                "protocol_report_consistency",
                "conclusion_supported_by_data",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.5,
            checks=[
                "alcoa_attributable",
                "alcoa_contemporaneous",
                "alcoa_original",
                "pre_execution_approval",
                "results_vs_criteria_comparison",
                "deviation_handling",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "acceptance_criteria_defined",
                "measurement_units_specified",
                "validation_runs_count",
                "critical_parameters_identified",
            ],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "requalification_schedule",
                "change_control_trigger",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.8,
            checks=[
                "regulatory_citation_coverage",
                "fda_pv_guidance_alignment",
                "annex_15_compliance",
                "gap_vs_current_regulations",
            ],
            required_context=["document_text", "regulatory_corpus", "company_agencies"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.2,
            checks=[
                "enforcement_pattern_match",
                "repeat_observation_risk",
                "severity_elevation",
                "failure_mode_match",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),
    },

    score_weights={
        "L1": 0.10,
        "L2": 0.05,
        "L3": 0.25,
        "L4": 0.20,
        "L5": 0.15,
        "L7": 0.05,
        "L8": 0.15,
        "L9": 0.05,
    },

    passing_threshold=75.0,  # Higher bar for validation documents
    sector_overlays={},
)
