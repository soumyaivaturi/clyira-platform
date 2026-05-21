"""
Enforcement Engine — Pattern matching against enforcement intelligence (L9).
Matches findings against Warning Letters, 483s, and other enforcement actions.
Elevates severity when a finding matches a known enforcement pattern.
"""
import logging
from typing import Optional

from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)


class EnforcementEngine:
    """
    Matches assessment findings against enforcement records.
    When a finding aligns with a known enforcement action pattern,
    severity is elevated and enforcement context is attached.
    """

    # Severity elevation rules
    ELEVATION_MAP = {
        "low": "medium",
        "medium": "high",
        "high": "critical",
        "critical": "critical",  # Already max
    }

    async def run(
        self, context: AssessmentContext, existing_findings: list[FindingResult]
    ) -> list[FindingResult]:
        """
        Run enforcement matching (L9).
        Searches for enforcement records matching the current findings.
        """
        if not context.enforcement_records:
            logger.info("No enforcement records available for matching")
            return []

        findings = []

        # For each enforcement record, check if any current finding aligns
        for record in context.enforcement_records:
            matched_finding = self._match_against_findings(record, existing_findings, context)
            if matched_finding:
                findings.append(matched_finding)

        return findings

    def _match_against_findings(
        self, record: dict, existing_findings: list[FindingResult], context: AssessmentContext
    ) -> Optional[FindingResult]:
        """Check if an enforcement record matches any existing finding"""
        record_categories = record.get("observation_categories", [])
        record_cfr = record.get("cfr_citations", [])

        for finding in existing_findings:
            # Match by category
            category_match = finding.category in record_categories
            # Match by CFR citation
            citation_match = any(
                cfr in (finding.regulatory_citation or "")
                for cfr in record_cfr
            )

            if category_match or citation_match:
                return FindingResult(
                    level="L9",
                    severity="high",
                    category="enforcement_pattern_match",
                    title=f"Enforcement pattern match: {record.get('title', 'Unknown')}",
                    description=(
                        f"This finding aligns with enforcement action {record.get('reference_number', '')} "
                        f"issued to {record.get('company_cited', 'another company')} on {record.get('issue_date', '')}. "
                        f"Similar observations have resulted in {record.get('outcome', 'enforcement action')}."
                    ),
                    evidence=f"Finding '{finding.title}' matches pattern in {record.get('record_type', '')} "
                             f"{record.get('reference_number', '')}",
                    regulatory_citation=finding.regulatory_citation or "",
                    citation_type="enforcement",
                    agency=record.get("agency", "FDA"),
                    enforcement_match=True,
                    enforcement_context=(
                        f"{record.get('record_type', '').replace('_', ' ').title()} "
                        f"{record.get('reference_number', '')} — "
                        f"{record.get('summary', '')[:200]}"
                    ),
                    confidence_score=0.85,
                    validated=True,
                )

        return None

    def elevate_severities(
        self, findings: list[FindingResult], enforcement_records: list[dict]
    ) -> list[FindingResult]:
        """
        Elevate severity of findings that match enforcement patterns.
        A finding whose category appears in trending enforcement patterns
        gets bumped up one severity level.
        """
        if not enforcement_records:
            return findings

        # Collect trending categories
        trending_categories = set()
        for record in enforcement_records:
            if record.get("trending", False):
                trending_categories.update(record.get("observation_categories", []))

        # Elevate matching findings
        for finding in findings:
            if finding.category in trending_categories and not finding.severity_elevated:
                original = finding.severity
                finding.severity = self.ELEVATION_MAP.get(finding.severity, finding.severity)
                if finding.severity != original:
                    finding.severity_elevated = True
                    finding.enforcement_context = (
                        f"Severity elevated from {original} to {finding.severity} "
                        f"due to trending enforcement pattern in category '{finding.category}'."
                    )

        return findings
