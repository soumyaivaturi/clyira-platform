"""
Sterile / Aseptic Pack — additional checks for sterile manufacturing.

Activates when: BatchDossier.is_sterile = True.
Adds L5 and L6 checks for EM data, filter integrity, sterilization, fill/finish.

Regulatory: 21 CFR 211, FDA Aseptic Processing Guidance (2004), EU GMP Annex 1 (2022).
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

STERILE_ASEPTIC_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1 additions: sterile-specific required documentation sections
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "aseptic_processing_records_present",   # Aseptic process documentation
            "environmental_monitoring_records_present",  # EM data for classified areas
            "filter_integrity_records_present",     # Filter integrity test records
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L5 additions: sterile-specific in-process compliance
    # ──────────────────────────────────────────────────────────────────────────
    "L5": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.6,
        checks=[
            "environmental_monitoring_classified_areas",  # Grade A/B/C/D EM data
            "filter_integrity_results",                   # Bubble point / diffusion pass
            "endotoxin_results_within_limits",            # LAL / rFC testing
            "sterility_test_results",                     # 14-day sterility test
            "particulate_matter_results",                 # Visible + sub-visible
            "intervention_log_completeness",              # Aseptic interventions documented
            "aseptic_hold_time_compliance",               # Hold time vs validated limits
            "fill_weight_volume_checks",                  # Fill weight/volume in spec
            "sterilization_cycle_parameters",             # Autoclave / depyrogenation records
            "container_closure_integrity_evidence",       # CCI documentation
            "visual_inspection_reconciliation",           # 100% visual inspection records
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L6 additions: sterile cross-reference checks
    # ──────────────────────────────────────────────────────────────────────────
    "L6": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.3,
        checks=[
            "em_data_cross_referenced_with_manufacturing_dates",  # EM excursion linkage
            "personnel_gowning_qualification_current",            # Gowning qual status
            "room_classification_verification",                   # Room classification confirmed
            "media_fill_reference_current",                       # Media fill qualification
            "bioburden_limits_pre_filtration",                    # Pre-filtration bioburden
        ],
        required_context=["document_text", "company_documents_metadata"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L8 additions: sterile regulatory compliance
    # ──────────────────────────────────────────────────────────────────────────
    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.6,
        checks=[
            "eu_gmp_annex_1_compliance",             # Sterile manufacturing requirements
            "aseptic_process_validation_reference",  # APV reference current
            "fda_aseptic_guidance_compliance",       # FDA 2004 aseptic guidance
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}
