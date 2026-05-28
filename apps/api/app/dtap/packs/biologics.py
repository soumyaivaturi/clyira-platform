"""
Biologics Pack — checks for biologics / vaccine batch records.

Activates for: Biologics batch records (combined with Pharma Drug Product Pack + Sterile Pack).
Adds: cell bank traceability, bioreactor parameters, purification, viral clearance.

Regulatory: 21 CFR 211 + ICH Q5A/Q5B/Q5C/Q5D/Q6B, EU GMP Annex 2.
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

BIOLOGICS_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1 additions: biologics-specific required documentation
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "cell_bank_seed_stock_records_present",    # Cell bank / seed lot
            "fermentation_cell_culture_records_present",  # Bioreactor parameters
            "purification_step_records_present",       # Column chromatography steps
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L5 additions: biologics in-process / analytical compliance
    # ──────────────────────────────────────────────────────────────────────────
    "L5": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.6,
        checks=[
            "cell_viability_within_limits",       # Viability at harvest
            "product_purity_results",              # Aggregation, charge variants
            "potency_results_within_spec",         # Bioassay / potency
            "residual_host_cell_protein",          # HCP within limits
            "residual_dna_within_limits",          # Host cell DNA limits
            "viral_clearance_step_parameters",    # Viral inactivation/removal records
            "hold_time_temperature_compliance",   # Hold time and temperature excursions
            "column_resin_cycle_count",           # Column reuse / resin cycle tracking
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L6 additions: biologics traceability
    # ──────────────────────────────────────────────────────────────────────────
    "L6": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.3,
        checks=[
            "cell_bank_lot_traceability",              # MCB/WCB lot linkage
            "bioburden_endotoxin_cross_reference",     # Bioburden/endotoxin data linkage
            "comparability_protocol_reference",        # Comparability if process change
            "column_cleaning_validation_reference",    # Column clean in place records
        ],
        required_context=["document_text", "company_documents_metadata"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L8 additions: biologics regulatory compliance
    # ──────────────────────────────────────────────────────────────────────────
    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.6,
        checks=[
            "ich_q5_compliance",                    # ICH Q5 quality of biotech products
            "ich_q6b_specifications_compliance",    # ICH Q6B specifications
            "bla_supplement_trigger_assessment",    # BLA supplement considerations
            "eu_gmp_annex_2_compliance",            # EU GMP Annex 2 biotech
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}
