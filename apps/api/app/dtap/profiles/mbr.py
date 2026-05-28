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

MBR_DTAP = DTAPProfile(
    dtap_id="DTAP-007",
    document_category="MBR",
    display_name="Master Batch Record / Batch Production Record",
    version="1.0",

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
    # LEVEL CONFIGURATIONS
    # ══════════════════════════════════════════════════════════════════════

    levels={
        # ──────────────────────────────────────────────────────────────────
        # L1: STRUCTURAL INTEGRITY — Are all mandatory elements present?
        # Engine: Rule (deterministic checks)
        # Regulatory: 21 CFR 211.186, 211.188
        # ──────────────────────────────────────────────────────────────────
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                # Standard structural check — verifies all required_sections exist
                "required_sections_present",

                # 21 CFR 211.186(a) — product must be identified by name,
                # strength, and dosage form
                "product_identification_complete",

                # 21 CFR 211.188(a) — batch number must be unique and traceable
                "batch_number_format",

                # 21 CFR 211.186(b)(2) — batch size and theoretical yield
                # with max/min percentages must be stated
                "batch_size_and_yield_range_specified",

                # 21 CFR 211.188(a) — record must be accurate reproduction of
                # approved MBR, checked for accuracy, dated, and signed
                "mbr_version_reference",

                # 21 CFR 211.188 — dates of manufacturing documented
                "manufacturing_date_recorded",

                # 21 CFR 211.137 — expiration or retest dating
                "expiry_or_retest_date_present",

                # Industry best practice (Assyro checklist: "all pages present,
                # numbered sequentially, and accounted for")
                "page_numbering_sequential",

                # 21 CFR 211.186(b)(1) — complete list of components,
                # designating by names or codes sufficiently specific
                "bill_of_materials_present",

                # 21 CFR 211.188(b)(5) — major equipment identified
                "equipment_list_present",
            ],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L2: DOCUMENT CONTROL — Version control, signatures, traceability
        # Engine: Rule
        # Regulatory: 21 CFR 211.186, 211.188(a), 211.192
        # ──────────────────────────────────────────────────────────────────
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.9,
            checks=[
                # 21 CFR 211.186 — MBR must be prepared, dated, and signed
                # by one person and independently checked by a second person
                "document_control_number",

                # Version traceability — executed record must reference
                # specific approved MBR version
                "revision_history",

                # 21 CFR 211.188(a) — accurate reproduction of MBR
                "executed_vs_master_version_match",

                # 21 CFR 211.188(b)(7) — identification of persons performing
                # and directly supervising or checking each significant step
                "operator_identification_complete",

                # 21 CFR 211.192 — QA must review and approve before release
                "qa_reviewer_signature_present",

                # 21 CFR 211.186 — independent check by second person
                "dual_signature_verification",

                # 21 CFR 211.188(b)(7) — supervisory sign-off
                "supervisory_approval_documented",
            ],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L3: CONTENT QUALITY — Are instructions specific and complete?
        # Engine: Hybrid (rule + LLM for semantic analysis)
        # Regulatory: 21 CFR 211.186(b)(4), 211.100(a)
        # ──────────────────────────────────────────────────────────────────
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.8,
            checks=[
                # 21 CFR 211.186(b)(4) — complete manufacturing and control
                # instructions, sampling and testing procedures, specifications
                "manufacturing_instructions_specificity",

                # ICH Q8, FDA Process Validation Guidance — CPPs must be
                # identified and controlled
                "critical_process_parameters_identified",

                # 21 CFR 211.186(b)(6) — sampling, testing procedures,
                # specifications for in-process materials
                "in_process_control_criteria_defined",

                # 21 CFR 211.194(a)(2) — acceptance criteria must be
                # quantitative, not vague ("satisfactory", "acceptable")
                "acceptance_criteria_quantitative",

                # GMP best practice — manufacturing steps must be in logical
                # order, each step building on previous
                "step_sequence_logical",

                # 21 CFR 211.186(b)(5) — special notations and precautions
                "special_precautions_documented",

                # Equipment operating parameters (temp, speed, pressure, time)
                # must be specified with ranges, not just target values
                "equipment_parameters_specified",

                # 21 CFR 211.186(b)(6) — sampling plan must define what,
                # when, how much, and acceptance criteria
                "sampling_plan_completeness",

                # 21 CFR 211.188(b)(3) — yield calculation methodology
                # must be clear and reproducible
                "yield_calculation_methodology",

                # Competitor insight (Acodis): check that BOM quantities
                # are specific (not ranges where exact values are required)
                "component_quantity_specificity",
            ],
            required_context=["document_text", "dtap_profile"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L4: DATA INTEGRITY (ALCOA+) — Is the data trustworthy?
        # Engine: Hybrid (rule for structural, LLM for semantic patterns)
        # Regulatory: 21 CFR 211.68, Part 11, FDA Data Integrity Guidance
        # This is the HIGHEST-weighted level for MBR because data integrity
        # is the #1 FDA concern for batch records and the most common 483
        # observation category.
        # ──────────────────────────────────────────────────────────────────
        "L4": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                # ALCOA — Attributable: every entry must identify who
                # performed the activity (21 CFR 211.188(b)(7))
                "alcoa_attributable",

                # ALCOA — Contemporaneous: data recorded at time of activity,
                # not back-filled later (EU GMP Ch4, MHRA DI guidance)
                "alcoa_contemporaneous",

                # ALCOA — Original: first-hand recording, not transcribed
                # from scratch paper or memory
                "alcoa_original",

                # GMP correction requirements — single line strikethrough,
                # NOT white-out, erasure, or overwrite
                # (Top 10 batch record error per Assyro, GMP Pros)
                "corrections_single_line_strikethrough",

                # Every correction must be initialed and dated by the
                # person making the correction
                "corrections_initialed_and_dated",

                # Reason for correction must be documented
                # (FDA 483 frequent citation: "corrections without explanations")
                "corrections_reason_documented",

                # 21 CFR Part 11 / EU Annex 11 — electronic records must
                # have audit trail showing original values
                "audit_trail_integrity",

                # No blank or incomplete fields — every required field
                # must be completed (N/A acceptable with justification)
                # (Top FDA 483: "incomplete entries" / "blank fields")
                "no_blank_required_fields",

                # Timestamps must be logically consistent — no time
                # travel (step 5 before step 4), no impossible gaps
                "timestamp_logical_consistency",

                # Data should not be identical across multiple independent
                # readings (copying detection)
                "duplicate_data_detection",
            ],
            required_context=["document_text", "dtap_profile"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L5: DATA INTELLIGENCE — Are values within expected ranges?
        # Engine: Hybrid
        # Regulatory: 21 CFR 211.103, 211.188(b)(3), 211.192
        # ──────────────────────────────────────────────────────────────────
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.4,
            checks=[
                # 21 CFR 211.103, 211.192 — actual yield compared against
                # theoretical yield; discrepancy outside max/min is an
                # automatic investigation trigger
                "yield_within_theoretical_range",

                # 21 CFR 211.188(b)(11) — in-process test results must
                # meet acceptance criteria
                "in_process_results_within_spec",

                # Environmental monitoring data (temp, humidity, differential
                # pressure, particulate) must be within validated limits
                "environmental_data_within_limits",

                # 21 CFR 211.188(b)(3) — percentage of theoretical yield
                # must be calculated at appropriate stages
                "interim_yield_calculations_present",

                # Process analytical technology / statistical monitoring —
                # where CPPs are recorded, are they trending within
                # validated ranges across the batch?
                "critical_parameter_range_compliance",

                # Hold time checks — intermediate hold times must not
                # exceed validated limits
                "hold_time_within_validated_limits",
            ],
            required_context=["document_text", "dtap_profile"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L6: CROSS-REFERENCE & TRACEABILITY — Are linked records connected?
        # Engine: LLM (semantic cross-reference analysis)
        # Regulatory: 21 CFR 211.84, 211.186(b)(1), 211.188
        # ──────────────────────────────────────────────────────────────────
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.2,
            checks=[
                # 21 CFR 211.84 — raw material testing and release;
                # lot numbers must trace back to approved supplier CoA
                "raw_material_lot_traceability",

                # Equipment cleaning validation — cleaning status must be
                # verified before use (line clearance)
                "equipment_cleaning_log_linkage",

                # Any deviation during manufacturing must reference the
                # deviation report number and investigation status
                "deviation_report_cross_reference",

                # If deviations exist, CAPA must be linked or justification
                # for no CAPA must be provided
                "capa_linkage_if_deviation",

                # 21 CFR 211.84(d) — component release status must be
                # confirmed; no use of quarantined materials
                "component_release_status_verified",

                # Supplier certificates of analysis should be referenced
                # for incoming materials
                "supplier_coa_referenced",

                # Stability protocol linkage — if batch is for stability,
                # protocol reference must be present
                "stability_protocol_linkage",

                # 21 CFR 211.188(b)(10) — labeling records including
                # specimens of labels used
                "labeling_reconciliation_documented",
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L7: LIFECYCLE & TIMELINESS — Are reviews and actions timely?
        # Engine: Rule
        # Regulatory: 21 CFR 211.192, 211.137, ICH Q10
        # ──────────────────────────────────────────────────────────────────
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                # 21 CFR 211.192 — batch record must be reviewed before
                # release; delayed reviews are a top 483 observation
                # (GMP Pros: "product shipped before QA approval complete")
                "batch_review_timeliness",

                # Deviations must be closed / investigated before batch
                # disposition decision is made
                "deviation_closure_before_release",

                # 21 CFR 211.137 — expiration dating must be supported
                # by stability data
                "expiry_dating_supported",

                # If reprocessing occurred, complete documentation per
                # 21 CFR 211.115 must be present
                "reprocessing_documentation_if_applicable",

                # Batch cannot be released with open action items
                "no_open_action_items_at_release",

                # 21 CFR 211.188(b)(3) — yield check timing; intermediate
                # and final yields must be calculated at defined steps
                "yield_check_timing_appropriate",
            ],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L8: REGULATORY COMPLIANCE — Does the record meet cGMP?
        # Engine: LLM (semantic regulatory alignment analysis)
        # Regulatory: 21 CFR 211 Subpart J, EU GMP Ch4, ICH Q7
        # ──────────────────────────────────────────────────────────────────
        "L8": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.5,
            checks=[
                # 21 CFR 211.186 — does the MBR contain all elements
                # required by the regulation?
                "cfr_211_186_mbr_compliance",

                # 21 CFR 211.188 — does the BPR contain complete
                # information relating to production and control?
                "cfr_211_188_bpr_compliance",

                # 21 CFR 211.192 — was production record review performed
                # by the quality control unit? Were discrepancies
                # investigated? Were investigations documented?
                "cfr_211_192_production_review_compliance",

                # EU GMP Chapter 4 — documentation principles including
                # contemporaneous recording, clear and legible records
                "eu_gmp_chapter_4_documentation_compliance",

                # ICH Q7 Section 6 — batch production records for APIs
                # (applicable if assessing API batch records)
                "ich_q7_batch_record_compliance",

                # 21 CFR Part 11 / EU Annex 11 — if electronic records,
                # are Part 11 controls in place?
                "electronic_record_compliance_if_applicable",

                # 21 CFR 211.192 — batch disposition must be justified
                # with reference to all completed reviews and investigations
                "batch_disposition_justified",

                # EU Annex 16 — QP certification requirements for EU release
                "qp_certification_elements_if_eu",
            ],
            required_context=["document_text", "regulatory_corpus", "company_agencies"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L9: ENFORCEMENT PATTERN MATCHING — Does this record match
        #     patterns that triggered FDA/EMA enforcement actions?
        # Engine: Hybrid (rule-based pattern + LLM for nuance)
        # Source: Clyira enforcement corpus (2,919+ observations)
        # ──────────────────────────────────────────────────────────────────
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.3,
            checks=[
                # General enforcement pattern matching against Clyira's
                # FDA warning letter observation corpus
                "enforcement_pattern_match",

                # Does this batch show patterns similar to previously
                # cited observations at same facility or product type?
                "repeat_observation_risk",

                # Severity elevation — are findings compounding to a
                # pattern that would escalate from 483 to warning letter?
                "severity_elevation",

                # Specific pattern: missing signatures — >70 Form 483s
                # in 2024 cited batch documentation failures (Leucine)
                "missing_signature_enforcement_pattern",

                # Specific pattern: data integrity — Ranbaxy, Cetero,
                # Able Labs enforcement patterns
                "data_integrity_enforcement_pattern",

                # Specific pattern: batch released without complete review
                # (21 CFR 211.192 violation — top warning letter driver)
                "premature_release_enforcement_pattern",

                # Specific pattern: yield discrepancy not investigated
                # (21 CFR 211.192 — unexplained discrepancy)
                "yield_discrepancy_enforcement_pattern",

                # FDA failure mode library match
                "failure_mode_match",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L10: LONGITUDINAL ANALYSIS — Cross-batch and trending
        # Engine: LLM (requires historical data)
        # Regulatory: 21 CFR 211.180(e) — annual product review;
        #             ICH Q10 — knowledge management and continual improvement
        # ──────────────────────────────────────────────────────────────────
        "L10": LevelConfig(
            enabled=True,
            engine="llm",
            weight=0.7,
            checks=[
                # Is this batch's yield trending differently from the
                # last N batches of the same product?
                "batch_to_batch_yield_trend",

                # Are similar deviations occurring across multiple batches?
                # (indicates systemic issue vs isolated event)
                "recurring_deviation_pattern",

                # Process capability trending — are CPPs drifting toward
                # specification limits even if still in range?
                "process_capability_trend",

                # Equipment-specific performance — is this equipment
                # associated with more deviations than others?
                "equipment_performance_trend",
            ],
            required_context=["historical_assessments"],
        ),

        # ──────────────────────────────────────────────────────────────────
        # L11: INSPECTABILITY — Would this survive an FDA inspection?
        # Engine: Rule (deterministic red-flag detection)
        # Context: FDA investigators reconstruct full batches using records
        #          to verify accuracy (GMP Pros)
        # ──────────────────────────────────────────────────────────────────
        "L11": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.0,
            checks=[
                # No placeholder text ("TBD", "to be determined", "pending")
                "no_tbd_placeholders",

                # No draft language ("draft", "for review", "preliminary")
                "no_draft_language",

                # Effective date must be present and valid
                "effective_date_present",

                # No unsigned signature lines — every signature block
                # must be completed (top FDA 483 observation)
                "blank_signature_lines",

                # Version control block must be complete
                "version_control_complete",

                # All pages must be present and accounted for
                # (Assyro checklist: "pages present, numbered sequentially")
                "all_pages_accounted_for",

                # Template language copied from MBR without being
                # populated with actual batch data
                "template_boilerplate_detection",

                # Date logic: manufacturing date < review date < release date;
                # no future dates, no impossible sequences
                "date_logic_consistency",

                # Internal consistency — values referenced in one section
                # must match values stated in another section
                "internal_cross_section_consistency",

                # Legibility indicators — document must not contain
                # indicators of illegible or ambiguous entries
                "legibility_indicators",
            ],
        ),
    },

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
