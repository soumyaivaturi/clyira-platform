"""
L10 Longitudinal Intelligence Engine — Repeat finding detection and score trend analysis.

Compares the current assessment against prior completed assessments for the same document.
Elevates severity when the same issue persists across multiple assessment cycles.
"""
import logging
from collections import defaultdict

from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)

# Severity escalation map: what to escalate TO when a finding repeats
_ESCALATION = {
    "info": "low",
    "low": "medium",
    "medium": "high",
    "high": "critical",
    "critical": "critical",
}


class LongitudinalEngine:
    """
    L10: Detects repeat findings across assessment cycles and generates trend findings.

    Logic:
    - A finding is considered 'recurring' if a finding with the same `category`
      appears in at least one prior completed assessment.
    - A finding that recurs while still open (not resolved) gets severity elevated
      by one band.
    - Generates one L10 meta-finding per recurring category group summarising
      the recurrence pattern.
    - Also generates an L10 score-trend finding if the Clyira score has declined
      over the last N assessments.
    """

    async def run(
        self,
        context: AssessmentContext,
        current_findings: list[FindingResult],
    ) -> list[FindingResult]:
        """
        Run longitudinal analysis. Returns new L10 findings (does not mutate current_findings).
        Severity elevation of recurring findings is handled by `elevate_recurring()`.
        """
        if not context.historical_assessments:
            return []

        l10_findings: list[FindingResult] = []

        # Build a map: category → list of historical assessments where this category appeared
        category_history: dict[str, list[dict]] = defaultdict(list)
        for hist in context.historical_assessments:
            for hf in hist.get("findings", []):
                category_history[hf["category"]].append({
                    "assessment_id": hist["assessment_id"],
                    "score": hist["score"],
                    "created_at": hist["created_at"],
                    "severity": hf["severity"],
                    "status": hf["status"],
                    "title": hf["title"],
                })

        # Current finding categories
        current_categories = {f.category for f in current_findings}

        # Score trend
        score_trend_finding = self._check_score_trend(context)
        if score_trend_finding:
            l10_findings.append(score_trend_finding)

        # Detect recurring findings
        for category in current_categories:
            occurrences = category_history.get(category, [])
            if not occurrences:
                continue

            # How many prior cycles contained this category?
            prior_cycle_count = len(set(o["assessment_id"] for o in occurrences))
            if prior_cycle_count < 1:
                continue

            # Get the representative current finding for this category
            representative = next((f for f in current_findings if f.category == category), None)
            if not representative:
                continue

            # Was it ever resolved in a prior cycle?
            ever_resolved = any(o["status"] == "resolved" for o in occurrences)
            most_recent_status = occurrences[-1]["status"] if occurrences else "unknown"
            was_open_last_cycle = most_recent_status in ("open", "acknowledged", "in_progress")

            # Only generate L10 meta-finding if it was previously unresolved
            if not ever_resolved and was_open_last_cycle:
                l10_findings.append(self._make_recurring_finding(
                    category=category,
                    representative=representative,
                    prior_cycle_count=prior_cycle_count,
                    occurrences=occurrences,
                ))

        logger.info(f"L10 longitudinal: {len(l10_findings)} findings from {len(context.historical_assessments)} historical assessments")
        return l10_findings

    def elevate_recurring(
        self,
        current_findings: list[FindingResult],
        context: AssessmentContext,
    ) -> list[FindingResult]:
        """
        Elevate severity of findings whose category persisted unresolved from prior cycles.
        Mutates and returns the findings list.
        """
        if not context.historical_assessments:
            return current_findings

        # Build unresolved category set from last assessment
        last_assessment = context.historical_assessments[0] if context.historical_assessments else {}
        unresolved_last_cycle = {
            f["category"]
            for f in last_assessment.get("findings", [])
            if f["status"] in ("open", "acknowledged", "in_progress")
        }

        for finding in current_findings:
            if finding.category in unresolved_last_cycle and finding.level != "L10":
                old_sev = finding.severity
                new_sev = _ESCALATION.get(old_sev, old_sev)
                if new_sev != old_sev:
                    finding.severity = new_sev
                    finding.severity_elevated = True
                    finding.description += (
                        f"\n\n[L10 Escalation] This finding recurred from the previous assessment "
                        f"cycle while still unresolved. Severity elevated from {old_sev} → {new_sev}."
                    )

        return current_findings

    def _check_score_trend(self, context: AssessmentContext) -> FindingResult | None:
        """Generate an L10 finding if the Clyira score has been declining across the last 3+ assessments."""
        scores = [h["score"] for h in context.historical_assessments if h.get("score") is not None]
        if len(scores) < 2:
            return None

        # Take last 3 scores (most recent first)
        recent = scores[:3]
        if all(recent[i] > recent[i + 1] for i in range(len(recent) - 1)):
            # Consistently declining
            drop = recent[-1] - recent[0]  # negative number
            cycle_count = len(recent)
            return FindingResult(
                level="L10",
                severity="high" if drop < -10 else "medium",
                category="score_declining_trend",
                title=f"Clyira Score declining over {cycle_count} consecutive assessment cycles",
                description=(
                    f"The document's Clyira Score has declined in each of the last {cycle_count} "
                    f"completed assessments (from {recent[-1]:.1f} to {recent[0]:.1f}, a change of "
                    f"{drop:.1f} points). A consistently declining score indicates that document quality "
                    f"issues are accumulating faster than they are being resolved. This trend, if "
                    f"unaddressed, will lower the company's aggregate readiness score and may attract "
                    f"regulatory scrutiny during an audit."
                ),
                evidence=f"Score history (most-recent first): {', '.join(f'{s:.1f}' for s in recent)}",
                regulatory_citation="ICH Q10 Section 3.2",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
                suggestion_draft=(
                    "Prioritize CAPA closure for open critical and high findings. "
                    "Run a targeted department review to address root causes of the declining score trend. "
                    "Consider a focused re-assessment after at least 3 findings are resolved."
                ),
            )

        # Check for score stagnation (no improvement over last 3 cycles while below 75)
        if len(recent) >= 3 and all(s < 75 for s in recent):
            variance = max(recent) - min(recent)
            if variance < 5:
                return FindingResult(
                    level="L10",
                    severity="medium",
                    category="score_stagnation",
                    title=f"Clyira Score stagnant below threshold for {len(recent)} consecutive assessments",
                    description=(
                        f"The document's Clyira Score has remained below 75 for {len(recent)} consecutive "
                        f"assessments, fluctuating only {variance:.1f} points (between "
                        f"{min(recent):.1f} and {max(recent):.1f}). Score stagnation below the "
                        f"passing threshold indicates that no material improvement is being driven by "
                        f"CAPA or document revision activities. This pattern is a systemic quality "
                        f"management concern — findings are being acknowledged but not resolved."
                    ),
                    evidence=f"Score history (most-recent first): {', '.join(f'{s:.1f}' for s in recent)}",
                    regulatory_citation="ICH Q10 Section 3.2",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.85,
                    validated=True,
                )

        return None

    def _make_recurring_finding(
        self,
        category: str,
        representative: FindingResult,
        prior_cycle_count: int,
        occurrences: list[dict],
    ) -> FindingResult:
        """Generate an L10 finding summarising the recurrence of a specific category."""
        cycle_word = f"{prior_cycle_count} prior assessment cycle{'s' if prior_cycle_count > 1 else ''}"
        severity = "critical" if prior_cycle_count >= 3 else ("high" if prior_cycle_count >= 2 else "medium")

        # Use the most severe original severity as context
        original_severities = [o["severity"] for o in occurrences]
        worst = next(
            (s for s in ("critical", "high", "medium", "low", "info") if s in original_severities),
            representative.severity,
        )

        return FindingResult(
            level="L10",
            severity=severity,
            category=f"recurring_{category}",
            title=f"Recurring unresolved finding: '{representative.title[:60]}' — {cycle_word}",
            description=(
                f"The finding '{representative.title}' (category: {category}) has appeared in {cycle_word} "
                f"of assessments for this document and was not resolved before the next assessment cycle. "
                f"Recurring unresolved findings represent a systemic quality management failure — they "
                f"indicate either that the CAPA implemented was ineffective, or that no corrective action "
                f"was taken. Under ICH Q10, recurring findings in the same category must trigger a "
                f"management review and an enhanced CAPA with a measurable effectiveness check."
            ),
            evidence=f"Found in {cycle_word}. Original severity: {worst}.",
            regulatory_citation="ICH Q10 Section 4.2 / 21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.88,
            validated=True,
            suggestion_draft=(
                f"1. Review the CAPA previously implemented for '{category}' — assess its effectiveness.\n"
                f"2. If the CAPA was implemented: escalate to management review and consider enhanced training "
                f"or process change.\n"
                f"3. If no CAPA was implemented: initiate a new CAPA with defined owner, due date, and "
                f"effectiveness criteria.\n"
                f"4. Document the recurrence in the Quality Management Review minutes."
            ),
        )
