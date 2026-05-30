"""
DTAP-008: QC Test Record / Certificate of Analysis Assessment Profile
Version 1.0 — Covers QC test records, COAs, OOS investigations, lab notebooks.

Regulatory grounding:
  - 21 CFR 211.192  — Production record review
  - 21 CFR 211.194  — Laboratory records
  - 21 CFR 211.68   — Automated laboratory equipment
  - FDA OOS Guidance (2006) — Out-of-specification results
  - ICH Q2(R1) — Validation of analytical procedures
  - USP <1225>  — Validation of compendial procedures
  - EU GMP Chapter 6 — Quality control

This DTAP assesses QC test records and COAs linked to batch dossiers.
It makes the BatchDossier's QC gate functional — the evidence completeness
gate requires QC results, and this profile provides their assessment.
"""
from app.dtap.profile import DTAPProfile, LevelConfig
from app.dtap.packs import compose_packs
from app.dtap.packs.core_production import CORE_PRODUCTION_LEVELS

# QC-specific overrides on top of core
_QC_EXTRA_LEVELS: dict[str, LevelConfig] = {
    "L1": LevelConfig(
        enabled=True,
        engine="rule",
        weight=1.0,
        checks=[
            "test_method_reference_present",        # Method number referenced
            "specification_reference_present",       # Specification reference cited
            "sample_identification_complete",        # Sample ID / lot number
            "analyst_identification_present",        # Analyst name / ID
            "instrument_identification_present",     # Instrument ID and calibration
            "test_results_recorded",                 # Results present for all tests
            "acceptance_criteria_stated",            # Pass/fail criteria defined
            "final_disposition_stated",              # Pass/Fail/OOS noted
        ],
    ),

    "L2": LevelConfig(
        enabled=True,
        engine="rule",
        weight=0.9,
        checks=[
            "lab_notebook_or_worksheet_reference",  # Raw data reference
            "review_by_second_analyst",             # Second person review
            "supervisor_approval_present",           # Lab supervisor sign-off
            "test_date_recorded",                   # Test execution date
            "report_date_recorded",                 # Report issuance date
        ],
    ),

    "L3": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.5,
        checks=[
            "system_suitability_criteria_met",      # SST criteria passed
            "system_suitability_documented",         # SST results in record
            "calculation_methodology_clear",         # Calculations reproducible
            "reference_standard_traceability",       # RS lot, purity, expiry
            "instrument_calibration_current",        # Cal date within interval
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    "L4": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=2.0,
        checks=[
            "alcoa_attributable",
            "alcoa_contemporaneous",
            "no_blank_required_fields",
            "corrections_single_line_strikethrough",
            "corrections_initialed_and_dated",
            "raw_data_preserved",                   # Original chromatograms / spectra kept
            "no_selective_result_reporting",        # All results reported (OOS guidance)
            "oos_investigation_documented_if_needed",  # OOS investigation present
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    "L5": LevelConfig(
        enabled=True,
        engine="hybrid",
        weight=1.6,
        checks=[
            "all_tests_pass_acceptance_criteria",   # Results within spec
            "oos_result_correctly_handled",         # OOS investigation per FDA guidance
            "oot_result_assessed",                  # OOT trending assessment
            "related_substances_within_limits",     # Impurity limits
            "assay_within_specification",           # Assay meets spec
            "microbial_results_within_limits",      # Micro / endotoxin if applicable
        ],
        required_context=["document_text", "dtap_profile"],
    ),

    "L6": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.2,
        checks=[
            "test_method_sop_cross_reference",      # Test method SOP cited and current
            "specification_document_linkage",        # Spec doc version matches
            "batch_record_cross_reference",          # Batch record for tested lot cited
            "stability_protocol_linkage",            # Stability protocol if stability sample
            "reference_standard_certificate_linkage",# RS CoA referenced
            "instrument_qualification_reference",    # Instrument IQ/OQ/PQ current
        ],
        required_context=["document_text", "company_documents_metadata"],
    ),

    "L8": LevelConfig(
        enabled=True,
        engine="llm",
        weight=1.4,
        checks=[
            "cfr_211_194_lab_records_compliance",   # 21 CFR 211.194
            "fda_oos_guidance_compliance",           # FDA OOS Guidance 2006
            "ich_q2_method_validation_reference",   # ICH Q2(R1)
            "usp_compendial_compliance",             # USP method compliance
        ],
        required_context=["document_text", "regulatory_corpus", "company_agencies"],
    ),
}

_QC_LEVELS = compose_packs(CORE_PRODUCTION_LEVELS, _QC_EXTRA_LEVELS)

QC_TEST_DTAP = DTAPProfile(
    dtap_id="DTAP-008",
    document_category="QC_TEST",
    display_name="QC Test Record / Certificate of Analysis",
    version="1.0",

    required_sections=[
        "Sample Identification",
        "Test Method Reference",
        "Specification Reference",
        "Test Results",
        "System Suitability",
        "Acceptance Criteria",
        "Analyst Signature",
        "Reviewer Approval",
    ],

    optional_sections=[
        "OOS/OOT Investigation Reference",
        "Raw Data Reference",
        "Instrument Maintenance Log",
        "Reference Standard Information",
        "Retest Results",
    ],

    section_order_matters=False,

    levels=_QC_LEVELS,

    score_weights={
        "L1": 0.10,  # Structural completeness
        "L2": 0.08,  # Document control
        "L3": 0.14,  # Content quality (SST, calculations)
        "L4": 0.22,  # Data integrity — highest (raw data, no selective reporting)
        "L5": 0.18,  # Results in spec / OOS handling
        "L6": 0.05,  # Cross-reference
        "L7": 0.06,  # Timeliness
        "L8": 0.10,  # Regulatory compliance
        "L9": 0.04,  # Enforcement patterns
        "L10": 0.02, # Longitudinal
        "L11": 0.01, # Inspectability
    },

    passing_threshold=75.0,
)
