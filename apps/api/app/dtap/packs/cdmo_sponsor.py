"""
CDMO Sponsor Oversight Pack — additional checks for CDMO-received lot packages.

Activates when: BatchDossier.manufacturing_context = "cdmo_received".
Adds checks for sponsor package completeness, quality agreement alignment,
CDMO-to-sponsor traceability, and dual-stage review workflow.

Regulatory: Sponsor quality agreement + applicable GMP regulations.
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

CDMO_SPONSOR_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1 additions: sponsor package required documents
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "sponsor_package_cover_letter_present",   # Package transmittal / cover
            "cdmo_internal_review_complete_indicator",# CDMO sign-off evident
            "sponsor_coa_present",                    # Certificate of Analysis included
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L3 additions: CDMO content quality checks
    # ──────────────────────────────────────────────────────────────────────────
    "L3": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.5,
        checks=[
            "cdmo_manufacturing_instructions_match_sponsor_mbs",  # Match sponsor MBS
            "cdmo_deviation_handling_per_quality_agreement",      # Dev handling per QA
            "change_notification_documented",                     # Changes notified to sponsor
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L6 additions: CDMO cross-reference and traceability
    # ──────────────────────────────────────────────────────────────────────────
    "L6": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.3,
        checks=[
            "sponsor_material_lot_traceability",          # Sponsor-provided material lots
            "cdmo_equipment_qualification_referenced",    # Equipment qualified per sponsor spec
            "quality_agreement_requirement_met",          # QA requirements fulfilled
            "coa_values_consistent_with_bpr",             # COA vs BPR value alignment
        ],
        required_context=["document_text", "company_documents_metadata"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L8 additions: CDMO regulatory obligations
    # ──────────────────────────────────────────────────────────────────────────
    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.4,
        checks=[
            "cdmo_gmp_compliance_certification",          # CDMO GMP cert
            "sponsor_regulatory_requirements_met",        # Sponsor regs satisfied
            "change_control_notification_compliant",      # Change control to sponsor
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}
