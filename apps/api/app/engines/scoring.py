"""
Scoring Engine — Calculates the Clyira Score from assessment findings.
Score = 100 - weighted_deductions_per_level
"""
import logging
from app.dtap.profile import DTAPProfile
from app.engines.types import FindingResult

logger = logging.getLogger(__name__)


# Severity deduction points
SEVERITY_DEDUCTIONS = {
    "critical": 15.0,
    "high": 8.0,
    "medium": 4.0,
    "low": 2.0,
    "info": 0.5,
}

# Score bands
SCORE_BANDS = [
    (90.0, "Excellent"),
    (80.0, "Good"),
    (65.0, "Moderate"),
    (50.0, "Poor"),
    (0.0, "Critical"),
]


class ScoringEngine:
    """
    Calculates Clyira Score based on findings and DTAP weights.

    Algorithm:
    1. Group findings by level
    2. For each level: sum deductions based on severity
    3. Apply level weight from DTAP
    4. Cap per-level deduction at the level's max weight contribution
    5. Final score = 100 - total_weighted_deductions
    """

    def calculate(self, findings: list[FindingResult], profile: DTAPProfile) -> dict:
        """Calculate the overall Clyira Score"""
        level_scores: dict[str, dict] = {}
        total_deduction = 0.0

        enabled_levels = profile.get_enabled_levels()

        for level in enabled_levels:
            level_findings = [f for f in findings if f.level == level]
            weight = profile.get_level_weight(level)

            # Calculate raw deduction for this level
            raw_deduction = sum(
                SEVERITY_DEDUCTIONS.get(f.severity, 0.0)
                for f in level_findings
            )

            # Cap deduction — a single level cannot tank the whole score
            max_level_deduction = weight * 100  # Max contribution proportional to weight
            capped_deduction = min(raw_deduction, max_level_deduction)

            # Weight the deduction
            weighted_deduction = capped_deduction * weight
            total_deduction += weighted_deduction

            # Per-level score (100 - deduction for that level)
            level_score = max(0.0, 100.0 - raw_deduction)

            level_scores[level] = {
                "score": round(level_score, 1),
                "findings_count": len(level_findings),
                "raw_deduction": round(raw_deduction, 1),
                "weighted_deduction": round(weighted_deduction, 2),
                "weight": weight,
            }

        # Final score
        final_score = max(0.0, min(100.0, 100.0 - total_deduction))
        score_band = self._get_band(final_score)

        logger.info(f"Score calculated: {final_score:.1f} ({score_band})")

        return {
            "score": round(final_score, 1),
            "score_band": score_band,
            "total_deduction": round(total_deduction, 1),
            "level_scores": level_scores,
            "findings_total": len(findings),
        }

    @staticmethod
    def _get_band(score: float) -> str:
        """Determine score band"""
        for threshold, band in SCORE_BANDS:
            if score >= threshold:
                return band
        return "Critical"

    def calculate_readiness_score(
        self, document_scores: list[dict], weights: dict[str, float] | None = None
    ) -> dict:
        """
        Calculate aggregated readiness score from multiple document scores.
        Used for department and company-level scoring.
        """
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
