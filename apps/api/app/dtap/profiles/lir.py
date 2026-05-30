"""
DTAP-005: Lab Investigation Report Assessment Profile
Covers OOS/OOT investigations per FDA OOS Guidance 2006.
11-dimensional assessment grounded in 21 CFR 211.192/211.194, FDA OOS Guidance 2006.

Changelog v1.2 (2026-05-30):
- Added human-reasoning checks per DTAP Design Guide v1 (four reasoning patterns)
- NARRATIVE COHERENCE: phase1_findings_support_assignable_cause,
  phase2_justified_by_phase1, root_cause_explains_oos_result,
  retest_conclusion_consistent_with_data
- PROPORTIONALITY: retest_sample_size_matches_risk,
  investigation_scope_covers_affected_batches, phase2_not_circumvented,
  no_premature_lab_error_conclusion
- CONSPICUOUS ABSENCE: stability_samples_not_addressed,
  other_analysts_not_checked_when_analyst_error, instrument_investigation_absent,
  method_investigation_absent_when_warranted
- INSPECTOR'S EYE: phase1_checklist_rubber_stamp, investigation_duration_credible,
  selective_result_exclusion, oos_rate_not_questioned
"""
from app.dtap.profile import DTAPProfile, LevelConfig

LIR_DTAP = DTAPProfile(
    dtap_id="DTAP-005",
    document_category="LIR",
    display_name="Lab Investigation Report (OOS/OOT)",
    version="1.2",
    mode="locked",

    required_sections=[
        "LIR Identification",
        "OOS Result Details",
        "Phase I Investigation",
        "Phase I Conclusion",
        "Root Cause Analysis",
        "Impact Assessment",
        "Batch Disposition",
        "QA Review and Approval",
    ],
    optional_sections=[
        "Phase II Investigation",
        "Phase II Retesting",
        "CAPA",
        "Field Alert Report Assessment",
        "Stability Impact Assessment",
    ],
    section_order_matters=False,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.5,
            checks=[
                "required_sections_present",
                "phase_structure",
                "lir_required_fields",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "approval_signatures",
                "qa_independence",
                "version_control_block",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "phase1_conclusion",
                "phase2_adequacy",
                "root_cause_evidence",
                "retest_documentation",
                "investigation_completeness",
                # ── NARRATIVE COHERENCE (v1.2) ──────────────────────────────
                # Does the OOS investigation story hold together end-to-end?
                "phase1_findings_support_assignable_cause",  # Phase I observations logically lead to
                                                              # the stated assignable cause — not a leap
                "phase2_justified_by_phase1",                # Phase II investigation is appropriate
                                                              # given the Phase I conclusion and data
                "root_cause_explains_oos_result",            # Root cause explains why THIS specific
                                                              # result was OOS — not just a generic lab
                                                              # error narrative
                "retest_conclusion_consistent_with_data",    # Pass/fail conclusion drawn from retest
                                                              # is consistent with the actual numbers
                                                              # recorded (not a pre-determined outcome)
                # ── PROPORTIONALITY (v1.2) ──────────────────────────────────
                # Is the investigation scope proportionate to the OOS risk?
                "retest_sample_size_matches_risk",           # Retest sample size appropriate for
                                                              # patient risk and batch size — minimal
                                                              # retest on high-risk product is a flag
                "investigation_scope_covers_affected_batches", # All potentially affected lots
                                                              # investigated — not just the failing lot
                "phase2_not_circumvented",                   # Phase II investigation not bypassed
                                                              # without documented scientific rationale
                "no_premature_lab_error_conclusion",         # Lab error (Phase I) not concluded
                                                              # before exhausting all Phase I checklist
                                                              # items (equipment, method, analyst)
                # ── CONSPICUOUS ABSENCE (v1.2) ──────────────────────────────
                # What should be here given the OOS context but isn't?
                "stability_samples_not_addressed",           # OOS on stability-indicating test but no
                                                              # stability impact assessment documented
                "other_analysts_not_checked_when_analyst_error", # Analyst error conclusion without
                                                              # assessing other analysts who used same
                                                              # method or instrument
                "instrument_investigation_absent",           # Instrument suspected or flagged but no
                                                              # formal instrument investigation or
                                                              # calibration/maintenance review
                "method_investigation_absent_when_warranted", # Method variability suspected but no
                                                              # method performance data or ruggedness
                                                              # review included in Phase I
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "selective_reporting",
                "alcoa_attributable",
                "alcoa_contemporaneous",
                "root_cause_named_evidence",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.4,
            checks=[
                "oos_result_vs_specification",          # OOS result clearly compared to spec limits
                "oot_trend_criteria_applied",           # OOT trending rules applied
                "retest_sample_size_justified",         # Retest sample size per FDA OOS guidance
                "statistical_comparison_original_retest", # Statistical comparison of original vs retest
                "confidence_interval_or_variability",   # Analytical variability documented
                "stability_impact_quantified",          # Impact on stability data assessed
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.2,
            checks=[
                "lir_to_deviation_linkage",             # Deviation report cross-referenced
                "lir_to_capa_linkage",                  # CAPA initiated if confirmed OOS
                "batch_record_cross_reference",         # Batch record for affected lot(s)
                "test_method_sop_reference",            # Analytical method SOP cited
                "stability_protocol_linkage",           # Stability protocol if stability sample
                "instrument_qualification_reference",   # Instrument IQ/OQ/PQ current
                "reference_standard_traceability",      # RS lot, purity, expiry
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "oos_30day_timeline",
                "phase2_pre_authorization",
                "capa_timeline_defined",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "passing_retest_assignable_cause",
                "disposition_consistency",
                "far_assessment",
                "patient_safety_assessment",
                "confirmed_oos_release",
                "regulatory_reporting_documented",
            ],
            required_context=["document_text", "regulatory_corpus"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.2,
            checks=[
                "enforcement_pattern_match",
                "repeat_observation_risk",
                "severity_elevation",
                "failure_mode_match",
            ],
            required_context=["findings_so_far", "enforcement_records"],
        ),
        "L10": LevelConfig(
            enabled=True,
            engine="llm",
            weight=0.8,
            checks=[
                "oos_frequency_by_product",            # OOS rate per product/method
                "oos_frequency_by_analyst",            # Analyst-specific OOS patterns
                "repeat_assignable_cause_pattern",     # Same root cause recurring
                "lab_error_vs_manufacturing_trend",    # Phase I vs Phase II outcome trends
                "method_performance_degradation",      # Method generating increasing OOS over time
            ],
            required_context=["historical_assessments"],
        ),
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
                # ── INSPECTOR'S EYE (v1.2) ──────────────────────────────────
                # Would this survive 10 minutes of adversarial FDA review?
                "phase1_checklist_rubber_stamp",         # Phase I checklist completed uniformly
                                                          # (all "No" boxes ticked without evidence
                                                          # that each item was genuinely checked)
                "investigation_duration_credible",       # OOS investigation timeline is plausible —
                                                          # complex multi-batch OOS resolved in <24h
                                                          # is a red flag for perfunctory review
                "selective_result_exclusion",            # Some results excluded from assessment
                                                          # without clear documented justification
                                                          # (cherry-picking pattern)
                "oos_rate_not_questioned",               # Analyst-specific OOS pattern exists but
                                                          # is not flagged or discussed in the
                                                          # investigation narrative
            ],
        ),
    },

    score_weights={
        "L1": 0.07,
        "L2": 0.04,
        "L3": 0.18,
        "L4": 0.16,
        "L5": 0.12,
        "L6": 0.08,
        "L7": 0.04,
        "L8": 0.18,
        "L9": 0.05,
        "L10": 0.05,
        "L11": 0.03,
    },

    passing_threshold=70.0,
    sector_overlays={},
)
