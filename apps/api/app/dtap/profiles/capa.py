"""
DTAP-002: CAPA Assessment Profile
Based on DTAP-002 v2.4 specification — CAPA as Decision Intelligence Engine.

Changelog v2.4 (2026-05-26):
- Added L11 to score_weights (was missing — caused zero-impact for placeholder/signature findings)
- Redistributed score_weights: L3 0.22→0.20, L8 0.16→0.14, added L11=0.04 (total=1.00)
- Added 30 new checks from LLM benchmark, sparring mode review, and FDA enforcement analysis
- Moved "Regulatory Reporting Assessment" and "Patient Safety Impact Assessment" to required_sections
- Increased severity deductions in scoring engine (40/15/5/2 vs 25/10/3/1)
- Added score cap rules for critical patterns (unsigned docs, placeholder dates, etc.)
"""
from app.dtap.profile import DTAPProfile, LevelConfig

CAPA_DTAP = DTAPProfile(
    dtap_id="DTAP-002",
    document_category="CAPA",
    display_name="Corrective and Preventive Action",
    version="2.4",

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
        "Regulatory Reporting Assessment",          # NEW v2.4 — promoted from optional
        "Patient Safety Impact Assessment",          # NEW v2.4
        "CAPA Closure",
    ],
    optional_sections=[
        "Risk Assessment",
        "Impact Assessment",
        "Extension Justification",
        "Related CAPAs",
        "Training Requirements",
        "Management Review Summary",                 # NEW v2.4
        "Annual Product Review Cross-Reference",     # NEW v2.4
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
                "capa_id",
                "action_owners_and_dates",
                "containment_section_present",         # NEW v2.4 — must exist as dedicated section
                "patient_safety_impact_section",       # NEW v2.4 — required even if "no impact"
                "regulatory_reporting_section",        # NEW v2.4 — must document assessment
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
                "unsigned_approvals",
                "duplicate_document_id",               # NEW v2.4 — detect reused CAPA numbers
                "batch_size_context_for_impact",        # NEW v2.4 — batch size needed for impact assessment
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
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
                "human_error_root_cause",
                "training_only_capa",
                "effectiveness_criteria",
                "retrospective_capa",
                "probable_vs_confirmed_root_cause",    # NEW v2.4 — Fresenius Kabi pattern
                "capa_scope_narrow_vs_systemic",       # NEW v2.4 — Wockhardt pattern
                "corrective_action_addresses_root_cause",  # NEW v2.4 — CA must trace to RC
                "preventive_action_system_level",      # NEW v2.4 — PA must be systemic, not local
                "rca_method_actually_applied",         # NEW v2.4 — naming Fishbone ≠ doing it
                "acceptance_criteria_quantitative",    # NEW v2.4 — no "satisfactory" or "acceptable"
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
                "oos_invalidation_basis",
                "testing_into_compliance",
                "synthetic_data_disclaimer",           # NEW v2.4 — "not an actual record" disclaimers
                "audit_trail_review_documented",       # NEW v2.4 — ALCOA+ trail review evidence
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
                "apr_pqr_cross_reference",             # NEW v2.4 — APR/PQR linkage
                "management_review_escalation",        # NEW v2.4 — ICH Q10 management review
                "supplier_capa_linkage",               # NEW v2.4 — if root cause is incoming material
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
                "capa_aging_check",                    # NEW v2.4 — Sun Pharma pattern: CAPAs >90 days
                "interim_containment_duration",        # NEW v2.4 — containment can't be indefinite
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
                "distributed_batch_disposition",       # NEW v2.4 — if batch released, what's the decision?
                "patient_safety_impact_explicit",      # NEW v2.4 — must explicitly state impact conclusion
                "market_action_assessment",            # NEW v2.4 — withdrawal/recall decision documented
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
                "failure_mode_match",
                "data_integrity_enforcement_pattern",  # NEW v2.4 — Ranbaxy/Cetero/Able Labs patterns
                "narrow_scope_enforcement_pattern",    # NEW v2.4 — Wockhardt equipment-only CAPA pattern
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
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                "no_tbd_placeholders",
                "no_draft_language",
                "effective_date_present",
                "blank_signature_lines",
                "version_control_complete",
                "template_boilerplate_detection",      # NEW v2.4 — identical text across docs
                "internal_consistency_check",          # NEW v2.4 — section contradictions
                "date_logic_consistency",              # NEW v2.4 — initiation < target < closure
            ],
        ),
    },

    # v2.4 score_weights — L11 added (was missing), L3/L8 reduced slightly to fit
    # Total = 1.00. L3 remains highest (root cause quality is #1 CAPA differentiator).
    score_weights={
        "L1": 0.06,
        "L2": 0.06,
        "L3": 0.20,   # was 0.22 — reduced 0.02 to fund L11
        "L4": 0.10,
        "L5": 0.08,
        "L6": 0.10,
        "L7": 0.08,
        "L8": 0.14,   # was 0.16 — reduced 0.02 to fund L11
        "L9": 0.10,
        "L10": 0.04,
        "L11": 0.04,  # NEW — placeholder/signature/draft findings now impact score
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
