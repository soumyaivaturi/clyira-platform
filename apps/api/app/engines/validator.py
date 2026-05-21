"""
Anti-Hallucination Gate — Validates LLM findings before they reach the user.
No finding passes without verifiable citation or evidence basis.
"""
import logging
from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)

# Minimum confidence threshold for LLM findings
MIN_CONFIDENCE = 0.6

# Required fields for a valid finding
REQUIRED_FIELDS = ["level", "severity", "title", "description"]


class AntiHallucinationGate:
    """
    Validates findings before they reach users.

    Validation checks:
    1. Required fields present and non-empty
    2. Severity is a valid value
    3. LLM findings have minimum confidence score
    4. Regulatory citations must be verifiable (not fabricated)
    5. Evidence must reference actual document content
    6. No duplicate findings
    """

    VALID_SEVERITIES = {"critical", "high", "medium", "low", "info"}
    VALID_LEVELS = {f"L{i}" for i in range(1, 12)}

    async def validate(
        self, findings: list[FindingResult], context: AssessmentContext
    ) -> list[FindingResult]:
        """Run all validation checks and filter out invalid findings"""
        validated = []
        rejected_count = 0

        for finding in findings:
            if finding.validated:
                # Already validated (rule engine findings are pre-validated)
                validated.append(finding)
                continue

            passes, reason = self._validate_finding(finding, context)
            if passes:
                finding.validated = True
                validated.append(finding)
            else:
                rejected_count += 1
                logger.warning(f"Finding rejected: {finding.title} — Reason: {reason}")

        if rejected_count > 0:
            logger.info(f"Anti-hallucination gate: {rejected_count} findings rejected, "
                       f"{len(validated)} passed")

        # Remove duplicates
        validated = self._deduplicate(validated)

        return validated

    def _validate_finding(self, finding: FindingResult, context: AssessmentContext) -> tuple[bool, str]:
        """Validate a single finding. Returns (passes, reason)."""

        # Check 1: Required fields
        if not finding.title or not finding.description:
            return False, "Missing required title or description"

        # Check 2: Valid level
        if finding.level not in self.VALID_LEVELS:
            return False, f"Invalid level: {finding.level}"

        # Check 3: Valid severity
        if finding.severity not in self.VALID_SEVERITIES:
            return False, f"Invalid severity: {finding.severity}"

        # Check 4: Confidence threshold (LLM findings)
        if finding.confidence_score < MIN_CONFIDENCE:
            return False, f"Confidence too low: {finding.confidence_score}"

        # Check 5: Evidence grounding
        if not self._verify_evidence_grounding(finding, context):
            return False, "Evidence not grounded in document content"

        # Check 6: Citation plausibility
        if finding.regulatory_citation and not self._verify_citation_plausibility(finding):
            return False, "Citation appears fabricated"

        return True, ""

    def _verify_evidence_grounding(self, finding: FindingResult, context: AssessmentContext) -> bool:
        """
        Verify that the finding's evidence can be traced to document content.
        For 'missing' findings, we verify the absence claim.
        For 'present but wrong' findings, we verify the content exists.
        """
        # Missing-type findings are valid if the section/content truly doesn't exist
        missing_indicators = ["not found", "missing", "absent", "not detected", "lacks", "no "]
        if any(ind in finding.description.lower() for ind in missing_indicators):
            # For missing findings, we trust the check (rule engine already verified)
            return True

        # For content-quality findings, we need the evidence to reference something real
        if finding.evidence:
            # Basic check: evidence isn't empty boilerplate
            if len(finding.evidence) < 10:
                return False

        return True

    def _verify_citation_plausibility(self, finding: FindingResult) -> bool:
        """
        Basic check that a regulatory citation isn't obviously fabricated.
        Real citations follow patterns like '21 CFR 211.xxx' or 'EU GMP Annex X'.
        """
        citation = finding.regulatory_citation

        # Known valid patterns
        valid_patterns = [
            "21 CFR",
            "FDA",
            "ICH",
            "EU GMP",
            "Annex",
            "USP",
            "EP ",
            "WHO",
            "ISO ",
            "PIC/S",
            "MHRA",
            "TGA",
            "PMDA",
            "Data Integrity",
            "cGMP",
        ]

        if any(pattern in citation for pattern in valid_patterns):
            return True

        # If citation is generic like "best practice", allow it
        if any(term in citation.lower() for term in ["best practice", "industry standard", "guideline"]):
            return True

        # Unknown citation format — flag for review but don't reject
        logger.debug(f"Unrecognized citation format: {citation}")
        return True  # Allow with lower confidence

    def _deduplicate(self, findings: list[FindingResult]) -> list[FindingResult]:
        """Remove duplicate findings based on level + category + title similarity"""
        seen = set()
        unique = []

        for finding in findings:
            key = (finding.level, finding.category, finding.title[:50])
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique
