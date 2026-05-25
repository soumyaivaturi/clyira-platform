"""
DTAP-004: Deviation Report Assessment Profile
Covers manufacturing deviations, process excursions, and environmental events.
9-dimensional assessment grounded in 21 CFR 211.192, ICH Q10, EU GMP Ch 8.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

DEVIATION_DTAP = DTAPProfile(
    dtap_id="DTAP-004",
    document_category="Deviation",
    display_name="Deviation Report",
    version="1.0",

    required_sections=[
        "Deviation Identification",
        "Event Description",
        "Immediate Containment",
        "Root Cause Analysis",
        "Impact Assessment",
        "Batch Disposition",
        "Corrective and Preventive Actions",
        "QA Review and Approval",
    ],
    optional_sections=[
        "Risk Assessment",
        "Field Alert Report Assessment",
        "Regulatory Reporting Assessment",
        "Extension Justification",
        "Related Deviations",
    ],
    section_order_matters=False,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "required_sections_present",
                "deviation_required_fields",
                "containment_documented",
                "batch_info_present",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "approval_signatures",
                "effective_date_present",
                "qa_independence",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "root_cause_depth",
                "human_error_root_cause",
                "capa_adequacy",
                "root_cause_evidence_cited",
                "impact_statements_supported",
                "consistency_checks",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.5,
            checks=[
                "impact_without_data",
                "alcoa_attributable",
                "disposition_before_investigation",
            ],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "deviation_timeliness",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.8,
            checks=[
                "far_assessment",
                "patient_safety_assessment",
                "regulatory_reporting_documented",
                "disposition_justified",
            ],
            required_context=["document_text", "regulatory_corpus"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.3,
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
        "L7": 0.05,
        "L8": 0.25,
        "L9": 0.10,
    },

    passing_threshold=70.0,
    sector_overlays={},
)
