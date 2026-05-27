"""
Scoring Engine — Calculates the Clyira Score from assessment findings.
Score = 100 - sum(level_score_weight × min(raw_level_deduction, 100))

Severity deductions: critical=40, high=15, medium=5, low=2
Action state discounting: resolved→0× weight, in_progress→0.5× weight
L4 data integrity hold: any critical L4 finding caps score at 50 and sets hold flag.
Score caps: critical pattern detection (unsigned docs, all-placeholder dates, etc.)
"""
import logging
from app.dtap.profile import DTAPProfile
from app.engines.types import FindingResult

logger = logging.getLogger(__name__)


# Phase 5 severity deductions — recalibrated for auditor-realistic scoring (v2.4)
# Previous (v2.3): 25/10/3/1 — produced inflated 90+ scores even for deficient documents
# Current: 40/15/5/2 — aligns with FDA auditor severity expectations
SEVERITY_DEDUCTIONS = {
    "critical": 40.0,
    "high": 15.0,
    "medium": 5.0,
    "low": 2.0,
    "info": 0.5,
}

# Action state deduction multipliers — resolved findings don't penalize score
ACTION_STATE_MULTIPLIERS = {
    "open": 1.0,
    "acknowledged": 1.0,
    "in_progress": 0.5,
    "resolved": 0.0,
    "disputed": 1.0,  # pending review — full weight until resolved
}

# Remediation priority mapping
SEVERITY_PRIORITY = {
    "critical": 1,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 3,
}

# Score bands — tightened for auditor-realistic expectations
SCORE_BANDS = [
    (90.0, "Excellent"),
    (80.0, "Good"),
    (65.0, "Moderate"),
    (50.0, "Poor"),
    (0.0, "Critical"),
]

# ── Score Caps for Critical Patterns ──
# When specific categories of findings are present, the score is capped
# regardless of the deduction math. This prevents a document with fundamental
# deficiencies from scoring well just because they happen to fall in low-weight levels.
SCORE_CAP_RULES = [
    {
        "name": "unsigned_document",
        "trigger_categories": ["blank_signatures"],
        "trigger_severity": "critical",
        "cap": 65.0,
        "reason": "Unsigned document cannot be considered approved — FDA 483 immediate observation",
    },
    {
        "name": "placeholder_dates",
        "trigger_categories": ["tbd_placeholders"],
        "trigger_severity": None,  # any severity
        "trigger_min_count": 3,
        "cap": 60.0,
        "reason": "Multiple TBD/placeholder entries indicate incomplete document — not inspection-ready",
    },
    {
        "name": "no_root_cause",
        "trigger_categories": ["root_cause_missing", "root_cause_superficial"],
        "trigger_severity": "critical",
        "cap": 55.0,
        "reason": "Missing or superficial root cause analysis — core CAPA deficiency per 21 CFR 211.192",
    },
    {
        "name": "synthetic_data_disclaimer",
        "trigger_categories": ["synthetic_data_disclaimer"],
        "trigger_severity": None,
        "cap": 40.0,
        "reason": "Document contains synthetic/test data disclaimer — not an actual controlled record",
    },
    {
        "name": "no_effectiveness_criteria",
        "trigger_categories": ["effectiveness_criteria_missing", "effectiveness_criteria_vague"],
        "trigger_severity": "critical",
        "cap": 60.0,
        "reason": "No measurable effectiveness criteria — cannot demonstrate CAPA closure per ICH Q10",
    },
    {
        "name": "template_boilerplate",
        "trigger_categories": ["template_boilerplate_detected"],
        "trigger_severity": None,
        "cap": 65.0,
        "reason": "Significant template boilerplate detected — document lacks scenario-specific content",
    },
]


class ScoringEngine:
    """
    Calculates Clyira Score based on findings and DTAP weights.

    Algorithm:
    1. Group findings by level
    2. For each level: sum severity deductions (with action-state multipliers)
    3. Cap per-level raw deduction at 100 to prevent overflow
    4. Multiply capped deduction by level score_weight from DTAP
    5. Final score = 100 - sum(weighted_level_deductions)
    6. L4 critical hold: cap score at 50 and set data_integrity_hold flag
    """

    def calculate(
        self,
        findings: list[FindingResult],
        profile: DTAPProfile,
        finding_statuses: dict[str, str] | None = None,
    ) -> dict:
        """
        Calculate the Clyira Score.
        finding_statuses: optional dict mapping finding title → status for action-state scoring.
        When None, all findings are treated as open.
        """
        level_scores: dict[str, dict] = {}
        total_deduction = 0.0
        data_integrity_hold = False

        enabled_levels = profile.get_enabled_levels()

        for level in enabled_levels:
            level_findings = [f for f in findings if f.level == level]
            weight = profile.score_weights.get(level, 0.0)

            # Detect L4 data integrity hold
            if level == "L4":
                if any(f.severity == "critical" for f in level_findings):
                    data_integrity_hold = True

            # Sum deductions with optional action-state multiplier
            raw_deduction = 0.0
            for f in level_findings:
                base = SEVERITY_DEDUCTIONS.get(f.severity, 0.0)
                if finding_statuses is not None:
                    # Use provided status map (keyed by title)
                    status = finding_statuses.get(f.title, "open")
                else:
                    # Default all to open at assessment time
                    status = "open"
                multiplier = ACTION_STATE_MULTIPLIERS.get(status, 1.0)
                raw_deduction += base * multiplier

            # Cap per-level raw deduction at 100 then apply level weight
            capped = min(raw_deduction, 100.0)
            weighted_deduction = capped * weight
            total_deduction += weighted_deduction

            # Per-level score for display (uncapped)
            display_raw = sum(SEVERITY_DEDUCTIONS.get(f.severity, 0.0) for f in level_findings)
            level_score = max(0.0, 100.0 - display_raw)

            level_scores[level] = {
                "score": round(level_score, 1),
                "findings_count": len(level_findings),
                "raw_deduction": round(raw_deduction, 1),
                "weighted_deduction": round(weighted_deduction, 2),
                "weight": weight,
            }

        final_score = max(0.0, min(100.0, 100.0 - total_deduction))

        # L4 hold caps score at 50 — data integrity issues prevent passing
        if data_integrity_hold:
            final_score = min(final_score, 50.0)

        # ── Apply Score Cap Rules for critical patterns ──
        applied_caps = []
        for cap_rule in SCORE_CAP_RULES:
            matching = [
                f for f in findings
                if f.category in cap_rule["trigger_categories"]
            ]
            # Severity filter (if specified)
            if cap_rule.get("trigger_severity"):
                matching = [f for f in matching if f.severity == cap_rule["trigger_severity"]]
            # Minimum count filter (if specified)
            min_count = cap_rule.get("trigger_min_count", 1)
            if len(matching) >= min_count:
                if final_score > cap_rule["cap"]:
                    logger.info(
                        f"Score cap applied: '{cap_rule['name']}' — "
                        f"capping {final_score:.1f} → {cap_rule['cap']:.1f} "
                        f"({cap_rule['reason']})"
                    )
                    final_score = cap_rule["cap"]
                    applied_caps.append({
                        "rule": cap_rule["name"],
                        "cap": cap_rule["cap"],
                        "reason": cap_rule["reason"],
                        "trigger_count": len(matching),
                    })

        score_band = self._get_band(final_score)
        logger.info(f"Score calculated: {final_score:.1f} ({score_band}), L4_hold={data_integrity_hold}, caps={len(applied_caps)}")

        suspended_reasons = []
        if data_integrity_hold:
            suspended_reasons.append(
                "Critical ALCOA+/Data Integrity finding detected (L4) — document score capped at 50"
            )
        for cap in applied_caps:
            suspended_reasons.append(f"{cap['rule']}: {cap['reason']} (capped at {cap['cap']})")

        return {
            "score": round(final_score, 1),
            "score_band": score_band,
            "total_deduction": round(total_deduction, 1),
            "level_scores": level_scores,
            "findings_total": len(findings),
            "data_integrity_hold": data_integrity_hold,
            "score_caps_applied": applied_caps if applied_caps else None,
            "suspended_reason": (
                " | ".join(suspended_reasons) if suspended_reasons else None
            ),
        }

    def calculate_from_db_findings(self, db_findings: list[dict], profile: DTAPProfile) -> dict:
        """
        Recompute score from DB finding records (with their current status).
        db_findings: list of dicts with keys: level, severity, status, title
        """
        # Build synthetic FindingResult list
        class _F:
            def __init__(self, d):
                self.level = d.get("level", "L1")
                self.severity = d.get("severity", "medium")
                self.title = d.get("title", "")
                self.category = d.get("category", "")

        synthetic = [_F(d) for d in db_findings]
        # Build status map by title
        statuses = {d.get("title", ""): d.get("status", "open") for d in db_findings}
        return self.calculate(synthetic, profile, finding_statuses=statuses)

    @staticmethod
    def get_remediation_priority(severity: str) -> int:
        return SEVERITY_PRIORITY.get(severity, 3)

    @staticmethod
    def _get_band(score: float) -> str:
        for threshold, band in SCORE_BANDS:
            if score >= threshold:
                return band
        return "Critical"

    def calculate_readiness_score(
        self, document_scores: list[dict], weights: dict[str, float] | None = None
    ) -> dict:
        """Aggregate readiness score from multiple document scores."""
        if not document_scores:
            return {"score": 0.0, "score_band": "Critical", "document_count": 0}

        total_weight = 0.0
        weighted_sum = 0.0

        for doc_score in document_scores:
            doc_weight = doc_score.get("weight", 1.0)
            weighted_sum += doc_score["score"] * doc_weight
            total_weight += doc_weight

        if total_weight == 0:
            return {"score": 0.0, "score_band": "Critical", "document_count": 0}

        aggregated_score = weighted_sum / total_weight
        return {
            "score": round(aggregated_score, 1),
            "score_band": self._get_band(aggregated_score),
            "document_count": len(document_scores),
        }
