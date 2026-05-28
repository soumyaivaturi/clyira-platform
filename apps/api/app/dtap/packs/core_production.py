"""
Core Production Record Pack — checks that apply to ALL production records regardless of sector.

Covers: universal GMP/GDP requirements per 21 CFR 211, EU GMP Chapter 4, ICH Q10, ALCOA+.
Activates for: Pharma BPR, API, Biologics, Sterile, Device DHR, Supplement, Cell Therapy, CDMO.
"""
from app.dtap.profile import LevelConfig

VERSION = "1.0"

CORE_PRODUCTION_LEVELS: dict[str, LevelConfig] = {
    # ──────────────────────────────────────────────────────────────────────────
    # L1: STRUCTURAL COMPLETENESS — universal elements all production records need
    # ──────────────────────────────────────────────────────────────────────────
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "required_sections_present",   # Section list defined per sector pack
            "batch_number_format",          # 21 CFR 211.188(a)
            "manufacturing_date_recorded",  # 21 CFR 211.188
            "page_numbering_sequential",    # ALCOA+ / Assyro checklist
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L2: DOCUMENT CONTROL — version traceability, signatures, approvals
    # ──────────────────────────────────────────────────────────────────────────
    "L2": LevelConfig(
        enabled=True,
        engine="rule",
        weight=0.9,
        checks=[
            "document_control_number",         # 21 CFR 211.186
            "revision_history",                # Version traceability
            "executed_vs_master_version_match",# 21 CFR 211.188(a)
            "operator_identification_complete", # 21 CFR 211.188(b)(7)
            "qa_reviewer_signature_present",   # 21 CFR 211.192
            "dual_signature_verification",     # 21 CFR 211.186 independent check
            "supervisory_approval_documented", # 21 CFR 211.188(b)(7)
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L4: DATA INTEGRITY (ALCOA+) — highest-weight level for batch records
    # ──────────────────────────────────────────────────────────────────────────
    "L4": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=2.0,
        checks=[
            "alcoa_attributable",               # ALCOA — who performed/recorded
            "alcoa_contemporaneous",            # ALCOA — recorded at time of activity
            "alcoa_original",                   # ALCOA — first-hand, not transcribed
            "corrections_single_line_strikethrough",  # GMP correction rules
            "corrections_initialed_and_dated",  # Every correction initialed + dated
            "corrections_reason_documented",    # Reason for correction documented
            "audit_trail_integrity",            # 21 CFR Part 11 / EU Annex 11
            "no_blank_required_fields",         # No blank required fields
            "timestamp_logical_consistency",    # No backdating / impossible sequences
            "duplicate_data_detection",         # No copied data across readings
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L7: LIFECYCLE & TIMELINESS — timely review, open items, expiry
    # ──────────────────────────────────────────────────────────────────────────
    "L7": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "batch_review_timeliness",              # 21 CFR 211.192 — review before release
            "deviation_closure_before_release",     # Deviations closed before disposition
            "expiry_dating_supported",              # 21 CFR 211.137
            "reprocessing_documentation_if_applicable",  # 21 CFR 211.115
            "no_open_action_items_at_release",      # No open action items at release
            "yield_check_timing_appropriate",       # 21 CFR 211.188(b)(3)
        ],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L9: ENFORCEMENT PATTERN MATCHING — FDA warning letter / 483 patterns
    # ──────────────────────────────────────────────────────────────────────────
    "L9": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.3,
        checks=[
            "enforcement_pattern_match",
            "repeat_observation_risk",
            "severity_elevation",
            "missing_signature_enforcement_pattern",
            "data_integrity_enforcement_pattern",
            "premature_release_enforcement_pattern",
            "yield_discrepancy_enforcement_pattern",
            "failure_mode_match",
        ],
        required_context=["findings_so_far", "enforcement_records"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L10: LONGITUDINAL ANALYSIS — cross-batch trends, recurring patterns
    # ──────────────────────────────────────────────────────────────────────────
    "L10": LevelConfig(
        enabled=True,
        engine="llm",
        weight=0.7,
        checks=[
            "batch_to_batch_yield_trend",
            "recurring_deviation_pattern",
            "process_capability_trend",
            "equipment_performance_trend",
        ],
        required_context=["historical_assessments"],
    ),

    # ──────────────────────────────────────────────────────────────────────────
    # L11: INSPECTABILITY — would this survive an FDA inspection?
    # ──────────────────────────────────────────────────────────────────────────
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
            "all_pages_accounted_for",
            "template_boilerplate_detection",
            "date_logic_consistency",
            "internal_cross_section_consistency",
            "legibility_indicators",
        ],
    ),
}
