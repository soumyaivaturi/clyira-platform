"""
DTAP-002: CAPA Assessment Profile
Based on DTAP-002 v2.3 specification — CAPA as Decision Intelligence Engine.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

CAPA_DTAP = DTAPProfile(
    dtap_id="DTAP-002",
    document_category="CAPA",
    display_name="Corrective and Preventive Action",
    version="2.3",

    required_sections=[
        "CAPA Identification",
        "Problem Statement",
        "Immediate Containment Actions",
        "Root Cause Investigation",
        "Root Cause Analysis Method",
        "Corrective Actions",
        "Preventive Actions",
        "Effectiveness Checks",
        "Implementation Plan",
        "Verification of Completion",
        "CAPA Closure",
    ],
    optional_sections=[
        "Risk Assessment",
        "Impact Assessment",
        "Regulatory Notification Assessment",
        "Extension Justification",
        "Related CAPAs",
        "Training Requirements",
    ],
    section_order_matters=True,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                "required_sections_present",
                "capa_number_format",
                "initiation_date",
                "target_completion_date",
                "classification_present",  # minor, major, critical
                "source_identification",  # audit, deviation, complaint, etc.
                "approval_chain_complete",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.9,
            checks=[
                "document_control_number",
                "revision_history",
                "cross_references_to_source",
                "timeline_entries",
                "owner_assignment",
                "department_identification",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.8,
            checks=[
                "root_cause_depth",  # Is RCA superficial or thorough?
                "5_why_completeness",
                "fishbone_categories_covered",
                "corrective_vs_preventive_distinction",
                "action_specificity",  # Are actions vague or measurable?
                "effectiveness_criteria_measurable",
                "timeline_realism",
                "containment_adequacy",
                "scope_appropriateness",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "evidence_of_investigation",
                "data_references_present",
                "batch_records_cited",
                "trend_data_referenced",
                "investigation_completeness",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.0,
            checks=[
                "metrics_defined_for_effectiveness",
                "statistical_justification",
                "sample_size_rationale",
                "monitoring_period_defined",
            ],
        ),
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.3,
            checks=[
                "related_capa_linkage",
                "deviation_capa_traceability",
                "sop_update_requirements",
                "training_record_linkage",
                "change_control_triggered",
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                "30_day_response_timeline",
                "extension_justification_if_overdue",
                "effectiveness_check_timing",
                "closure_criteria_met",
                "recurrence_monitoring_period",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.6,
            checks=[
                "regulatory_reporting_assessment",
                "field_alert_consideration",
                "recall_assessment",
                "hhe_evaluation",
                "agency_notification_timeline",
                "cfr_compliance_211_192",
            ],
            required_context=["document_text", "regulatory_corpus", "company_agencies"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.5,
            checks=[
                "enforcement_pattern_match",
                "repeat_observation_risk",
                "severity_elevation",
                "consent_decree_pattern",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),
        "L10": LevelConfig(
            enabled=True,
            engine="llm",
            weight=0.8,
            checks=[
                "recurrence_pattern",
                "effectiveness_history",
                "capa_aging_analysis",
                "department_trend",
            ],
            required_context=["historical_assessments"],
        ),
        "L11": LevelConfig(
            enabled=False,
            engine="rule",
            weight=0.5,
            checks=[],
        ),
    },

    score_weights={
        "L1": 0.06,
        "L2": 0.06,
        "L3": 0.22,
        "L4": 0.10,
        "L5": 0.08,
        "L6": 0.10,
        "L7": 0.08,
        "L8": 0.16,
        "L9": 0.10,
        "L10": 0.04,
    },

    passing_threshold=70.0,

    sector_overlays={
        "SS-B1": {
            "L8_extra_checks": ["biologics_reporting_requirements", "bla_supplement_trigger"],
        },
        "SS-D1": {
            "L8_extra_checks": ["anda_supplement_trigger", "bioequivalence_impact"],
        },
    },
)
