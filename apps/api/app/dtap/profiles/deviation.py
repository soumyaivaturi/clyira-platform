"""
DTAP-004: Deviation Report Assessment Profile
Covers manufacturing deviations, process excursions, and environmental events.
11-dimensional assessment grounded in 21 CFR 211.192, ICH Q10, EU GMP Ch 8.

Changelog v1.2 (2026-05-30):
- Added human-reasoning checks per DTAP Design Guide v1 (four reasoning patterns)
- CONSPICUOUS ABSENCE: distributed_batches_not_addressed, stability_impact_absent,
  other_products_same_line, no_risk_assessment_for_critical, prior_deviations_ignored,
  no_regulatory_reporting_for_critical
- PROPORTIONALITY: containment_proportionate_to_severity, investigation_scope_vs_event,
  capa_proportionate_to_classification, premature_no_impact, disposition_before_rc
- NARRATIVE COHERENCE: rc_explains_event, impact_consistent_with_event_scope,
  containment_addresses_immediate_risk, capa_follows_from_rc
- INSPECTOR'S EYE: event_description_vague_or_sanitized, investigation_timeline_credible,
  qa_challenge_evidence, template_deviation_language
- Added sector overlays for sterile (SS-ST) and biologics (SS-BIO)
"""
from app.dtap.profile import DTAPProfile, LevelConfig

DEVIATION_DTAP = DTAPProfile(
    dtap_id="DTAP-004",
    document_category="Deviation",
    display_name="Deviation Report",
    version="1.2",
    mode="locked",

    required_sections=[
        "Deviation Identification",
        "Event Description",
        "Immediate Containment",
        "Root Cause Analysis",
        "Impact Assessment",
        "Batch Disposition",
        "Corrective and Preventive Actions",
        "QA Review and Approval",
    ],
    optional_sections=[
        "Risk Assessment",
        "Field Alert Report Assessment",
        "Regulatory Reporting Assessment",
        "Extension Justification",
        "Related Deviations",
    ],
    section_order_matters=False,

    levels={
        "L1": LevelConfig(
            enabled=True,
            engine="rule",
            weight=1.2,
            checks=[
                "required_sections_present",
                "deviation_required_fields",
                "containment_documented",
                "batch_info_present",
            ],
        ),
        "L2": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "approval_signatures",
                "effective_date_present",
                "qa_independence",
            ],
        ),
        "L3": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=2.0,
            checks=[
                "root_cause_depth",
                "human_error_root_cause",
                "capa_adequacy",
                "root_cause_evidence_cited",
                "impact_statements_supported",
                "consistency_checks",
                # ── NARRATIVE COHERENCE (v1.2) ──────────────────────────────
                # Does the deviation story hold together end-to-end?
                "rc_explains_event",                   # Root cause logically explains the specific
                                                        # event described — not just plausible in general
                "impact_consistent_with_event_scope",  # Impact assessment scope matches the actual
                                                        # event — a line-wide excursion can't have
                                                        # single-batch impact
                "containment_addresses_immediate_risk", # Containment action targets the immediate
                                                        # risk from this specific event, not generic
                "capa_follows_from_rc",                 # CAPA actions logically follow from the
                                                        # identified root cause — not boilerplate
                # ── PROPORTIONALITY & RED FLAGS (v1.2) ──────────────────────
                # Is the response proportionate to what happened?
                "containment_proportionate_to_severity", # Critical deviation with minimal containment
                                                          # is disproportionate — and vice versa
                "investigation_scope_vs_event",          # Multi-batch/multi-line event investigated
                                                          # as if single-batch is a red flag
                "capa_proportionate_to_classification",  # Major/Critical deviation closed with
                                                          # retraining-only is disproportionate
                "premature_no_impact",                   # "No impact" concluded without supporting
                                                          # data or before investigation complete
                "disposition_before_rc",                 # Batch disposition decided before root
                                                          # cause was established
                # ── CONSPICUOUS ABSENCE (v1.2) ──────────────────────────────
                # What should be here given the context but isn't?
                "distributed_batches_not_addressed",     # Affected batches already distributed but
                                                          # no market action assessment documented
                "stability_impact_absent",               # Deviation affects stability-relevant parameter
                                                          # but no stability impact assessment
                "other_products_same_line",               # Root cause involves line/equipment but no
                                                          # assessment of other products on same line
                "no_risk_assessment_for_critical",        # Critical/Major deviation with no formal
                                                          # risk assessment documented
                "prior_deviations_ignored",               # Similar prior deviations exist but are not
                                                          # referenced or addressed in this investigation
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L4": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.5,
            checks=[
                "impact_without_data",
                "alcoa_attributable",
                "disposition_before_investigation",
            ],
        ),
        "L5": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.2,
            checks=[
                "batch_impact_quantified",             # Number of affected batches documented
                "yield_impact_assessed",               # Yield deviation quantified
                "statistical_justification_if_claimed", # Claims of "within normal" backed by data
                "affected_batch_range_identified",      # All impacted lots enumerated
                "sample_size_rationale_for_assessment", # Assessment sample size justified
            ],
            required_context=["document_text", "dtap_profile"],
        ),
        "L6": LevelConfig(
            enabled=True,
            engine="llm",
            weight=1.3,
            checks=[
                "deviation_to_capa_linkage",           # CAPA initiated and cross-referenced
                "change_control_triggered_if_needed",  # Change control opened when warranted
                "related_deviation_cross_reference",   # Prior similar deviations cited
                "sop_referenced_for_process",          # Relevant SOP identified
                "batch_record_cross_reference",        # Batch record(s) cited
                "training_record_linkage",             # Retraining documented if human error
            ],
            required_context=["document_text", "company_documents_metadata"],
        ),
        "L7": LevelConfig(
            enabled=True,
            engine="rule",
            weight=0.8,
            checks=[
                "deviation_timeliness",
            ],
        ),
        "L8": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.8,
            checks=[
                "far_assessment",
                "patient_safety_assessment",
                "regulatory_reporting_documented",
                "disposition_justified",
                # ── CONSPICUOUS ABSENCE — REGULATORY (v1.2) ─────────────────
                "no_regulatory_reporting_for_critical",  # Critical deviation with patient safety
                                                          # implications but no regulatory reporting
                                                          # assessment (FAR, MedWatch, etc.)
            ],
            required_context=["document_text", "regulatory_corpus"],
        ),
        "L9": LevelConfig(
            enabled=True,
            engine="hybrid",
            weight=1.3,
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
            weight=0.7,
            checks=[
                "recurring_deviation_pattern",         # Same deviation type repeated
                "department_trend_analysis",           # Department-level deviation frequency
                "root_cause_category_trend",           # Same root cause appearing across deviations
                "escalation_trajectory",               # Are deviations becoming more severe?
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
                "event_description_vague_or_sanitized",  # Event description uses vague language
                                                          # ("may have", "possibly") or omits key
                                                          # details an inspector would ask about
                "investigation_timeline_credible",       # Investigation timeline is plausible —
                                                          # complex multi-batch event resolved in
                                                          # <24h is a red flag
                "qa_challenge_evidence",                  # QA review shows evidence of independent
                                                          # challenge, not rubber-stamp approval
                "template_deviation_language",            # Deviation uses identical/near-identical
                                                          # language across sections suggesting
                                                          # template fill rather than genuine analysis
            ],
        ),
    },

    score_weights={
        "L1": 0.08,
        "L2": 0.04,
        "L3": 0.20,
        "L4": 0.15,
        "L5": 0.10,
        "L6": 0.10,
        "L7": 0.04,
        "L8": 0.18,
        "L9": 0.05,
        "L10": 0.03,
        "L11": 0.03,
    },

    passing_threshold=70.0,
    sector_overlays={
        "SS-ST": {  # Sterile Manufacturing
            "additional_required_sections": ["Environmental Monitoring Data", "Media Fill Impact"],
            "L3_extra_checks": [
                "aseptic_breach_assessment",            # Was aseptic technique compromised?
                "environmental_excursion_scope",        # EM data for affected cleanroom areas
                "media_fill_invalidation_assessment",   # Does deviation invalidate recent media fill?
                "sterility_assurance_impact",           # Impact on SAL documented
            ],
            "L8_extra_checks": [
                "sterile_product_patient_risk",         # Heightened patient safety bar for sterile
            ],
        },
        "SS-BIO": {  # Biologics Manufacturing
            "additional_required_sections": ["Cell Bank Impact Assessment"],
            "L3_extra_checks": [
                "cell_line_contamination_assessment",   # Risk to cell bank/working cell bank
                "viral_clearance_impact",               # Deviation impact on viral clearance steps
                "bioburden_excursion_assessment",        # Bioburden impact for biologics
                "comparability_impact",                  # Does deviation trigger comparability study?
            ],
            "L8_extra_checks": [
                "bla_supplement_trigger",                # Does deviation require BLA supplement?
            ],
        },
    },
)
