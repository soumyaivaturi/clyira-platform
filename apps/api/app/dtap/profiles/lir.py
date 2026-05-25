"""
DTAP-005: Lab Investigation Report Assessment Profile
Covers OOS/OOT investigations per FDA OOS Guidance 2006.
9-dimensional assessment grounded in 21 CFR 211.192/211.194, FDA OOS Guidance 2006.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

LIR_DTAP = DTAPProfile(
    dtap_id="DTAP-005",
    document_category="LIR",
    display_name="Lab Investigation Report (OOS/OOT)",
    version="1.0",

    required_sections=[
        "LIR Identification",
        "OOS Result Details",
        "Phase I Investigation",
        "Phase I Conclusion",
        "Root Cause Analysis",
        "Impact Assessment",
        "Batch Disposition",
        "QA Review and Approval",
    ],
    optional_sections=[
        "Phase II Investigation",
        "Phase II Retesting",
        "CAPA",
        "Field Alert Report Assessment",
        "Stability Impact Assessment",
    ],
    section_order_matters=False,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.5,
            checks=[
                "required_sections_present",
                "phase_structure",
                "lir_required_fields",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "approval_signatures",
                "qa_independence",
                "version_control_block",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "phase1_conclusion",
                "phase2_adequacy",
                "root_cause_evidence",
                "retest_documentation",
                "investigation_completeness",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "selective_reporting",
                "alcoa_attributable",
                "alcoa_contemporaneous",
                "root_cause_named_evidence",
            ],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "oos_30day_timeline",
                "phase2_pre_authorization",
                "capa_timeline_defined",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "passing_retest_assignable_cause",
                "disposition_consistency",
                "far_assessment",
                "patient_safety_assessment",
                "confirmed_oos_release",
                "regulatory_reporting_documented",
            ],
            required_context=["document_text", "regulatory_corpus"],
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
        "L4": 0.22,
        "L7": 0.05,
        "L8": 0.26,
        "L9": 0.07,
    },

    passing_threshold=70.0,
    sector_overlays={},
)
