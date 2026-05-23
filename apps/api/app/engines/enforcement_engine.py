"""
Enforcement Engine — BM25 matching against FDA Warning Letters (L9).

For each finding, searches 2,919 Warning Letter observations via BM25
and attaches the most relevant precedent as enforcement_context.

Severity elevation thresholds (CFR citation frequency across the corpus):
  ≥ 25 observations  → elevate one level (low→medium, medium→high, high→critical)
  ≥ 45 observations  → force severity to critical

A single L9 finding is created per unique CFR section that exceeds the
≥25 threshold, summarising the enforcement risk for that citation.
"""
import logging
from app.engines.types import AssessmentContext, FindingResult
from app.engines import rag_engine

logger = logging.getLogger(__name__)

_FREQ_ELEVATE = 25    # observations needed to elevate one severity level
_FREQ_CRITICAL = 45   # observations needed to force critical

_ELEVATION_MAP = {
    "low": "medium",
    "medium": "high",
    "high": "critical",
    "critical": "critical",
}


class EnforcementEngine:
    """
    Annotates existing findings with FDA Warning Letter precedent and elevates
    severity based on CFR citation frequency. Returns new L9 findings for CFR
    sections that breach enforcement frequency thresholds.
    """

    ELEVATION_MAP = _ELEVATION_MAP

    async def run(
        self, context: AssessmentContext, existing_findings: list[FindingResult]
    ) -> list[FindingResult]:
        """
        Annotate existing_findings in-place; return new L9 enforcement-pattern findings.

        Mutation: sets enforcement_match, enforcement_context, severity_elevated, severity
        on findings whose CFR citation is high-frequency in the Warning Letter corpus.
        """
        if not existing_findings:
            return []

        l9_findings: list[FindingResult] = []
        seen_cfr_l9: set[str] = set()   # one L9 finding per unique CFR section

        for finding in existing_findings:
            cfr = (finding.regulatory_citation or "").strip()

            # BM25 search: title + CFR citation as query for best retrieval
            query = f"{finding.title} {cfr}".strip()
            precedents = rag_engine.search(query, n_results=2, cfr_filter=cfr or None)

            if precedents:
                finding.enforcement_match = True
                finding.enforcement_context = rag_engine.format_enforcement_excerpt(precedents)

            # CFR frequency-based severity elevation
            if cfr:
                freq = rag_engine.get_cfr_observation_count(cfr)

                if freq >= _FREQ_CRITICAL:
                    original = finding.severity
                    finding.severity = "critical"
                    if not finding.severity_elevated:
                        finding.severity_elevated = True
                        prefix = (
                            f"⚠ Severity elevated to critical: {cfr} appears in {freq} "
                            f"FDA Warning Letters — top enforcement priority.\n\n"
                        )
                        finding.enforcement_context = prefix + (finding.enforcement_context or "")
                    if cfr not in seen_cfr_l9:
                        seen_cfr_l9.add(cfr)
                        l9_findings.append(
                            self._make_l9_finding(cfr, freq, precedents, "critical")
                        )

                elif freq >= _FREQ_ELEVATE and not finding.severity_elevated:
                    original = finding.severity
                    elevated = _ELEVATION_MAP.get(finding.severity, finding.severity)
                    if elevated != original:
                        finding.severity = elevated
                        finding.severity_elevated = True
                        prefix = (
                            f"⚠ Severity elevated from {original} to {elevated}: "
                            f"{cfr} appears in {freq} FDA Warning Letters.\n\n"
                        )
                        finding.enforcement_context = prefix + (finding.enforcement_context or "")
                    if cfr not in seen_cfr_l9:
                        seen_cfr_l9.add(cfr)
                        l9_findings.append(
                            self._make_l9_finding(cfr, freq, precedents, elevated)
                        )

        if l9_findings:
            logger.info(f"Enforcement engine: {len(l9_findings)} L9 findings, "
                        f"{sum(1 for f in existing_findings if f.enforcement_match)} findings annotated")

        return l9_findings

    def _make_l9_finding(
        self,
        cfr: str,
        freq: int,
        precedents: list[dict],
        severity: str,
    ) -> FindingResult:
        company = precedents[0]['company'] if precedents else "multiple companies"
        year = precedents[0]['year'] if precedents else ""
        office = precedents[0]['office'] if precedents else "FDA"
        excerpt = precedents[0]['text'][:400] if precedents else ""
        return FindingResult(
            level="L9",
            severity=severity,
            category="enforcement_pattern_match",
            title=f"High-frequency enforcement pattern: {cfr} ({freq} FDA Warning Letters)",
            description=(
                f"{cfr} appears in {freq} FDA Warning Letters — placing this in the top enforcement "
                f"risk categories tracked by Clyira's corpus. FDA investigators specifically target "
                f"this deficiency category during inspections. Companies with this finding unresolved "
                f"face elevated Warning Letter and 483 observation risk. "
                f"Recent example: {company} ({office}, {year})."
            ),
            evidence=excerpt,
            regulatory_citation=cfr,
            citation_type="enforcement",
            agency="FDA",
            enforcement_match=True,
            enforcement_context=rag_engine.format_enforcement_excerpt(precedents),
            severity_elevated=True,
            confidence_score=0.95,
            validated=True,
        )

    def elevate_severities(
        self, findings: list[FindingResult], enforcement_records: list[dict]
    ) -> list[FindingResult]:
        # Elevation is now handled inside run() via CFR frequency.
        # This method is kept for orchestrator compatibility; enforcement_records
        # is always empty in the BM25 path, so we just return unchanged.
        return findings
