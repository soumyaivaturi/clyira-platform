"""
DTAP-003: Analytical Test Method Assessment Profile
Based on DTAP-005-LIR specification — OOS/OOT and method documentation.
"""
from app.dtap.profile import DTAPProfile, LevelConfig

ATM_DTAP = DTAPProfile(
    dtap_id="DTAP-003",
    document_category="ATM",
    display_name="Analytical Test Method",
    version="1.0",

    required_sections=[
        "Title and Scope",
        "Principle of Method",
        "Reagents and Reference Standards",
        "Equipment and Apparatus",
        "Sample Preparation",
        "Procedure",
        "System Suitability",
        "Calculations",
        "Reporting",
        "References",
    ],
    optional_sections=[
        "Safety and Handling",
        "Method Validation Summary",
        "OOS/OOT Investigation Procedure",
        "Stability Indicating Notes",
        "Transfer Protocol References",
        "Impurity Identification",
    ],
    section_order_matters=True,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                "required_sections_present",
                "method_number_format",
                "effective_date",
                "pharmacopoeia_reference",
                "equipment_list_completeness",
                "reagent_grade_specifications",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "version_control",
                "approval_signatures",
                "training_requirements",
                "method_validation_reference",
                "change_history",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.6,
            checks=[
                "procedure_specificity",
                "step_by_step_clarity",
                "critical_parameters_identified",
                "acceptance_criteria_unambiguous",
                "system_suitability_criteria_complete",
                "calculation_formula_correctness",
                "units_consistency",
                "sample_preparation_completeness",
                "system_suitability",
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.4,
            checks=[
                "alcoa_recording_instructions",
                "raw_data_requirements",
                "chromatogram_retention",
                "integration_parameters",
                "rounding_rules",
                "significant_figures",
                "data_backup_requirements",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.5,
            checks=[
                "oos_investigation_trigger_defined",
                "oot_trend_criteria",
                "phase_i_phase_ii_structure",
                "assignable_cause_categories",
                "retest_retake_criteria",
                "statistical_tools_specified",
                "cpk_ppk_references",
            ],
            required_context=["document_text", "regulatory_corpus"],
        ),
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.2,
            checks=[
                "pharmacopoeia_alignment",
                "compendial_vs_non_compendial",
                "cross_reference_to_specs",
                "related_method_consistency",
                "stability_protocol_linkage",
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "revalidation_triggers_defined",
                "periodic_review_schedule",
                "instrument_qualification_linkage",
                "standard_expiry_tracking",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.5,
            checks=[
                "usp_ep_jp_alignment",
                "ich_q2_compliance",
                "21_cfr_211_160_compliance",
                "data_integrity_per_annexes",
                "pharmacopoeia_monograph_match",
                "validation_declaration",
                "oos_trigger",
            ],
            required_context=["document_text", "regulatory_corpus", "company_agencies"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.3,
            checks=[
                "oos_enforcement_patterns",
                "lab_data_integrity_citations",
                "method_validation_deficiencies",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),
        "L10": LevelConfig(
            enabled=True,
            engine="llm",
            weight=0.6,
            checks=[
                "method_performance_trend",
                "oos_frequency_analysis",
                "analyst_variability_trend",
            ],
            required_context=["historical_assessments"],
        ),
        "L11": LevelConfig(
            enabled=True,  # ATMs are often submission-relevant
            engine="hybrid",
            weight=1.0,
            checks=[
                "ectd_module_3_format",
                "method_description_completeness",
                "validation_report_linkage",
                "specification_alignment",
            ],
        ),
    },

    score_weights={
        "L1": 0.06,
        "L2": 0.05,
        "L3": 0.16,
        "L4": 0.14,
        "L5": 0.14,
        "L6": 0.10,
        "L7": 0.05,
        "L8": 0.15,
        "L9": 0.08,
        "L10": 0.03,
        "L11": 0.04,
    },

    passing_threshold=70.0,

    sector_overlays={
        "SS-B1": {
            "L5_extra_checks": ["bioassay_specific_oos", "potency_trend_monitoring"],
        },
        "SS-B4": {  # Cell & Gene Therapy
            "additional_required_sections": ["Biosafety Level Requirements"],
            "L3_extra_checks": ["identity_testing_for_cell_products"],
        },
    },
)
