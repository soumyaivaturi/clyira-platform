"""
DTAP-007: Master Batch Record (MBR) / Batch Production Record (BPR) Assessment Profile
Version 1.0 — Batch Record Review for Manufacturing Lot Disposition.

Regulatory grounding:
  - 21 CFR 211.186  — Master production and control records
  - 21 CFR 211.188  — Batch production and control records
  - 21 CFR 211.192  — Production record review (QA review before release)
  - 21 CFR 211.194  — Laboratory records
  - 21 CFR Part 11   — Electronic records and electronic signatures
  - EU GMP Chapter 4 — Documentation
  - EU GMP Annex 11  — Computerised systems
  - EU GMP Annex 15  — Qualification and validation
  - EU GMP Annex 16  — Certification by a Qualified Person and batch release
  - ICH Q7 §6        — Documentation and records (APIs)
  - ICH Q10          — Pharmaceutical quality system
  - ALCOA+ principles — Data integrity framework

Industry context:
  - 60-70% of pharma companies still review batch records via paper/PDF (Acodis 2025)
  - 70%+ of QA effort goes into reviewing documentation, not investigations (EY)
  - 21% of FDA warning letters relate to documentation problems (GMP Pros)
  - 50% of product quality issues linked to human error in manual record handling (FDA)
  - Top FDA 483 patterns: missing signatures, incomplete data, delayed reviews,
    data integrity issues, yield discrepancies, correction errors
  - April 2026: FDA issued first warning letter citing AI misuse in batch record
    generation (Purolea Cosmetics Lab — 21 CFR 211.22(c))

Design informed by competitor analysis:
  - Acodis: automated signature/value/process-step checks, customizable business rules,
    deviation flagging, cross-batch comparison, 60-80% review time reduction
  - Tulip: review-by-exception (RBE) workflows, critical vs minor exception classification,
    MES/QMS/eBR integration, automated data point verification
  - Assyro AI: 7-category review checklist (pre-review, component, manufacturing step,
    in-process control, signature, deviation, correction/amendment)
  - GMP Pros: step-by-step review SOP, KPI benchmarks, risk-based review approaches
  - BizData360: AI document understanding for extraction + validation + analysis

This DTAP assesses uploaded MBR/BPR documents (PDF, DOCX) through Clyira's
L1-L11 neuro-symbolic engine. It does NOT execute batches — it reviews the
documentation for completeness, compliance, and inspection-readiness.
The human QA reviewer makes the final disposition decision.
"""
from app.dtap.profile import DTAPProfile, LevelConfig
from app.dtap.packs import compose_packs
from app.dtap.packs.core_production import CORE_PRODUCTION_LEVELS
from app.dtap.packs.pharma_drug_product import PHARMA_DRUG_PRODUCT_LEVELS

# Compose the pharma BPR profile from Core + Pharma Drug Product packs
_MBR_LEVELS = compose_packs(CORE_PRODUCTION_LEVELS, PHARMA_DRUG_PRODUCT_LEVELS)

MBR_DTAP = DTAPProfile(
    dtap_id="DTAP-007",
    document_category="MBR",
    display_name="Master Batch Record / Batch Production Record",
    version="1.1",

    # ──────────────────────────────────────────────────────────────────────
    # Required Sections
    # Grounded in 21 CFR 211.186 (MBR requirements) and 211.188 (BPR
    # requirements). Each section maps to a specific regulatory obligation.
    # ──────────────────────────────────────────────────────────────────────
    required_sections=[
        # 21 CFR 211.186(a) — product name, strength, description, dosage form
        "Product Identification",

        # 21 CFR 211.186(b)(1) — complete list of components with quantities
        "Bill of Materials",

        # 21 CFR 211.186(b)(2) — theoretical yield with max/min percentages
        "Batch Size and Theoretical Yield",

        # 21 CFR 211.186(b)(4) — complete manufacturing and control instructions
        "Manufacturing Instructions",

        # 21 CFR 211.186(b)(6) — sampling and testing procedures
        "In-Process Controls and Sampling",

        # 21 CFR 211.186(b)(3) — description of containers, closures, labeling
        "Packaging and Labeling",

        # 21 CFR 211.188(b)(5) — identification of major equipment used
        "Equipment Identification",

        # 21 CFR 211.188(b)(3) — actual yield and % of theoretical yield
        "Yield Calculations",

        # 21 CFR 211.188(a) — documentation of each significant step
        "Line Clearance and Equipment Cleaning",

        # 21 CFR 211.188(b)(11) — results of examinations
        "Environmental Monitoring Records",

        # 21 CFR 211.192 — QC unit review + disposition decision
        "Batch Disposition and QA Review",

        # 21 CFR 211.188(b)(7) — identification of persons performing each step
        "Signatures and Approvals",
    ],

    # ──────────────────────────────────────────────────────────────────────
    # Optional Sections
    # Present in well-structured batch records but not always separate sections.
    # ──────────────────────────────────────────────────────────────────────
    optional_sections=[
        "Deviation Summary",
        "Change Control References",
        "Reprocessing or Rework Documentation",
        "Stability Sampling Records",
        "Process Validation Reference",
        "Operator Training Verification",
        "Environmental Excursion Summary",
        "Raw Material Certificates of Analysis",
        "Hold Time Records",
        "Residual Solvent or Cleaning Verification",
    ],

    section_order_matters=True,

    # ══════════════════════════════════════════════════════════════════════
    # LEVEL CONFIGURATIONS — composed from Core + Pharma Drug Product packs
    # See: app/dtap/packs/core_production.py + app/dtap/packs/pharma_drug_product.py
    # ══════════════════════════════════════════════════════════════════════

    levels=_MBR_LEVELS,

    # ══════════════════════════════════════════════════════════════════════
    # SCORE WEIGHTS — How each level contributes to the Clyira Score
    #
    # Rationale for MBR weighting:
    #   L4 (Data Integrity) is highest because data integrity is the #1
    #   FDA enforcement concern for batch records, and the most common
    #   category of 483 observations and warning letters.
    #
    #   L3 (Content Quality) and L8 (Regulatory Compliance) are next
    #   because incomplete instructions and regulatory gaps directly
    #   impact whether the batch can be released.
    #
    #   L5 (Data Intelligence) captures yield and in-process compliance —
    #   critical for 211.192 disposition decisions.
    #
    #   Total must equal 1.00.
    # ══════════════════════════════════════════════════════════════════════
    score_weights={
        "L1": 0.08,   # Structural completeness
        "L2": 0.05,   # Document control
        "L3": 0.16,   # Content quality (instructions, CPPs, sampling)
        "L4": 0.18,   # Data integrity (ALCOA+) — highest weight
        "L5": 0.12,   # Data intelligence (yields, in-process, env)
        "L6": 0.10,   # Cross-reference and traceability
        "L7": 0.06,   # Lifecycle and timeliness
        "L8": 0.12,   # Regulatory compliance
        "L9": 0.06,   # Enforcement pattern matching
        "L10": 0.03,  # Longitudinal / trending analysis
        "L11": 0.04,  # Inspectability (red-flag detection)
    },

    # Higher threshold than default (70.0) because batch records are
    # release-critical documents — a non-compliant batch record directly
    # blocks product distribution per 21 CFR 211.192
    passing_threshold=75.0,

    # ══════════════════════════════════════════════════════════════════════
    # SECTOR OVERLAYS — Manufacturing type-specific additional checks
    # ══════════════════════════════════════════════════════════════════════
    sector_overlays={
        # Oral Solid Dosage — tablets, capsules
        "SS-OSD": {
            "L3_extra_checks": [
                "blend_uniformity_sampling",     # Content uniformity during blending
                "compression_parameters",        # Hardness, thickness, friability targets
                "coating_parameters",            # Pan speed, spray rate, inlet/outlet temps
                "granulation_endpoint",          # Granulation end-point criteria specified
            ],
            "L5_extra_checks": [
                "dissolution_profile_compliance",  # Dissolution results within spec
                "weight_variation_within_limits",   # Individual tablet/capsule weights
                "content_uniformity_results",       # Assay per unit dose
            ],
        },

        # Sterile / Injectable
        "SS-ST": {
            "additional_required_sections": [
                "Aseptic Processing Records",
                "Environmental Monitoring — Classified Areas",
                "Filter Integrity Test Records",
            ],
            "L3_extra_checks": [
                "media_fill_reference",           # Media fill qualification current
                "bioburden_limits_specified",      # Pre-filtration bioburden limits
                "sterilization_parameters",        # Autoclave/depyrogenation parameters
                "fill_weight_check_frequency",     # Fill volume/weight check intervals
            ],
            "L5_extra_checks": [
                "environmental_monitoring_classified_areas",  # Grade A/B/C/D monitoring
                "filter_integrity_results",                   # Bubble point / diffusion
                "endotoxin_results",                          # LAL / rFC testing
                "sterility_test_results",                     # 14-day sterility test
                "particulate_matter_results",                 # Visible and sub-visible
            ],
            "L8_extra_checks": [
                "aseptic_process_validation_reference",
                "eu_gmp_annex_1_compliance",    # Sterile manufacturing requirements
            ],
        },

        # Biologics — cell culture, fermentation, purification
        "SS-BIO": {
            "additional_required_sections": [
                "Cell Bank / Seed Stock Records",
                "Fermentation / Cell Culture Parameters",
                "Purification Step Records",
            ],
            "L3_extra_checks": [
                "cell_culture_parameters",        # pH, DO, temperature, viability
                "purification_step_sequence",     # Chromatography, filtration steps
                "viral_clearance_documentation",  # Viral inactivation/removal steps
                "potency_assay_methodology",      # Bioassay methodology specified
            ],
            "L5_extra_checks": [
                "cell_viability_within_limits",
                "product_purity_results",          # Aggregation, charge variants
                "potency_results_within_spec",
                "residual_host_cell_protein",
                "residual_dna_within_limits",
            ],
            "L8_extra_checks": [
                "bla_supplement_trigger",           # BLA supplement considerations
                "ich_q5_compliance",                # Quality of biotechnological products
                "comparability_assessment_if_change",
            ],
        },
    },
)
