"""
Pharma Drug Product Pack — sector-specific checks for pharmaceutical BPR/BMR.

Activates for: Pharma BMR/BPR, Biologics (combined with Biologics Pack).
Adds: L1 pharma structural checks, L3 content quality, L5 data intelligence,
      L6 cross-reference traceability, L8 regulatory compliance.

Regulatory grounding: 21 CFR 211.186, 211.188, 211.192, EU GMP Ch4/Annex 16, ICH Q10.
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

PHARMA_DRUG_PRODUCT_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1 additions: pharma-specific structural elements
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "product_identification_complete",   # 21 CFR 211.186(a)
            "batch_size_and_yield_range_specified",  # 21 CFR 211.186(b)(2)
            "mbr_version_reference",             # 21 CFR 211.188(a)
            "expiry_or_retest_date_present",     # 21 CFR 211.137
            "bill_of_materials_present",         # 21 CFR 211.186(b)(1)
            "equipment_list_present",            # 21 CFR 211.188(b)(5)
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L3: CONTENT QUALITY — specificity and completeness of instructions
    # ──────────────────────────────────────────────────────────────────────────
    "L3": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.8,
        checks=[
            "manufacturing_instructions_specificity",  # 21 CFR 211.186(b)(4)
            "critical_process_parameters_identified",  # ICH Q8, FDA PV Guidance
            "in_process_control_criteria_defined",     # 21 CFR 211.186(b)(6)
            "acceptance_criteria_quantitative",        # 21 CFR 211.194(a)(2)
            "step_sequence_logical",                   # GMP best practice
            "special_precautions_documented",          # 21 CFR 211.186(b)(5)
            "equipment_parameters_specified",          # Operating ranges required
            "sampling_plan_completeness",              # 21 CFR 211.186(b)(6)
            "yield_calculation_methodology",           # 21 CFR 211.188(b)(3)
            "component_quantity_specificity",          # Acodis best practice
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L5: DATA INTELLIGENCE — values within expected ranges
    # ──────────────────────────────────────────────────────────────────────────
    "L5": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.4,
        checks=[
            "yield_within_theoretical_range",       # 21 CFR 211.103, 211.192
            "in_process_results_within_spec",        # 21 CFR 211.188(b)(11)
            "environmental_data_within_limits",      # Validated EM limits
            "interim_yield_calculations_present",    # 21 CFR 211.188(b)(3)
            "critical_parameter_range_compliance",   # CPP monitoring
            "hold_time_within_validated_limits",     # Hold time validation
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L6: CROSS-REFERENCE & TRACEABILITY — linked documents and records
    # ──────────────────────────────────────────────────────────────────────────
    "L6": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.2,
        checks=[
            "raw_material_lot_traceability",     # 21 CFR 211.84
            "equipment_cleaning_log_linkage",    # Line clearance verification
            "deviation_report_cross_reference",  # Deviation number linkage
            "capa_linkage_if_deviation",         # CAPA linked to deviations
            "component_release_status_verified", # 21 CFR 211.84(d)
            "supplier_coa_referenced",           # CoA references for materials
            "stability_protocol_linkage",        # Stability protocol reference
            "labeling_reconciliation_documented",# 21 CFR 211.188(b)(10)
        ],
        required_context=["document_text", "company_documents_metadata"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L8: REGULATORY COMPLIANCE — cGMP alignment checks
    # ──────────────────────────────────────────────────────────────────────────
    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.5,
        checks=[
            "cfr_211_186_mbr_compliance",               # 21 CFR 211.186
            "cfr_211_188_bpr_compliance",               # 21 CFR 211.188
            "cfr_211_192_production_review_compliance", # 21 CFR 211.192
            "eu_gmp_chapter_4_documentation_compliance",# EU GMP Ch4
            "ich_q7_batch_record_compliance",           # ICH Q7 §6
            "electronic_record_compliance_if_applicable",# 21 CFR Part 11
            "batch_disposition_justified",              # 21 CFR 211.192
            "qp_certification_elements_if_eu",          # EU Annex 16
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}
