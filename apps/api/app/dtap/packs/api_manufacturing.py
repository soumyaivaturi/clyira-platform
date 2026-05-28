"""
API Manufacturing Pack — checks for Active Pharmaceutical Ingredient batch records.

Activates for: API batch records.
Primary regulatory reference: ICH Q7 (Good Manufacturing Practice Guide for APIs).

Adds: reaction parameters, intermediate testing, solvent tracking, impurity monitoring.
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

API_MANUFACTURING_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1 additions: API-specific required documentation
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "reaction_step_records_present",        # Reaction/process step records
            "intermediate_testing_records_present", # Intermediate testing
            "solvent_usage_records_present",        # Solvent usage and recovery
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L5 additions: API process compliance
    # ──────────────────────────────────────────────────────────────────────────
    "L5": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.5,
        checks=[
            "reaction_parameters_within_ranges",    # Temperature, pH, time in spec
            "intermediate_testing_results",         # Intermediate quality checks
            "solvent_usage_and_recovery_tracking",  # Solvent mass balance
            "impurity_profile_monitoring",          # Related substances monitoring
            "reprocessing_rework_documentation",    # Reprocess/rework if applicable
            "yield_at_each_synthesis_step",         # Step-wise yield tracking
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L8: API regulatory compliance — ICH Q7 as primary reference
    # ──────────────────────────────────────────────────────────────────────────
    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.5,
        checks=[
            "ich_q7_section6_batch_record_compliance",  # ICH Q7 §6 documentation
            "ich_q7_section8_in_process_controls",      # ICH Q7 §8 IPC requirements
            "eu_gmp_part_ii_compliance",                # EU GMP Part II for APIs
            "impurity_limits_justified",                # ICH Q3A/Q3C limits
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}
