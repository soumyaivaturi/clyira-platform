"""
Enforcement Engine — BM25 matching against FDA Warning Letters (L9).

For each finding, searches across all loaded enforcement corpora via BM25:
  1. FDA Warning Letters + Form 483s (rag_engine — domestic, highest weight)
  2. International enforcement actions (international_enforcement_engine)
  3. Regulatory corpus for citation context (regulatory_corpus_engine)

Severity elevation logic:
  ≥ 25 FDA observations  → elevate one level
  ≥ 45 FDA observations  → force critical
  Multi-agency match bonus: if same pattern found at 2+ agencies, apply extra elevation

A single L9 finding is created per unique CFR section that exceeds the ≥25 threshold.
"""
import logging
from app.engines.types import AssessmentContext, FindingResult
from app.engines import rag_engine
from app.engines import international_enforcement_engine
from app.engines import regulatory_corpus_engine

logger = logging.getLogger(__name__)

_FREQ_ELEVATE = 25
_FREQ_CRITICAL = 45

_ELEVATION_MAP = {
    "low": "medium",
    "medium": "high",
    "high": "critical",
    "critical": "critical",
}

# Minimum international score (0-1) to count as a cross-agency match
_INTL_SCORE_THRESHOLD = 0.6


class EnforcementEngine:
    """
    Annotates existing findings with enforcement precedent from all available sources
    and elevates severity based on CFR frequency + multi-agency corroboration.
    """

    ELEVATION_MAP = _ELEVATION_MAP

    async def run(
        self, context: AssessmentContext, existing_findings: list[FindingResult]
    ) -> list[FindingResult]:
        """
        Annotate existing_findings in-place; return new L9 enforcement-pattern findings.

        Mutation: sets enforcement_match, enforcement_context, severity_elevated, severity
        on findings whose CFR citation is high-frequency in the corpus.
        """
        if not existing_findings:
            return []

        l9_findings: list[FindingResult] = []
        seen_cfr_l9: set[str] = set()

        for finding in existing_findings:
            cfr = (finding.regulatory_citation or "").strip()
            query = f"{finding.title} {cfr}".strip()

            # ── 1. FDA domestic search (primary) ──────────────────────────────
            fda_precedents = rag_engine.search(query, n_results=2, cfr_filter=cfr or None)

            # ── 2. International search (secondary) ───────────────────────────
            intl_results = international_enforcement_engine.search(query, n_results=2)
            intl_matches = [r for r in intl_results if r['score'] >= _INTL_SCORE_THRESHOLD]

            # ── 3. Regulatory corpus context for citations ─────────────────────
            reg_context = ""
            if cfr:
                reg_results = regulatory_corpus_engine.search(cfr, n_results=1, cfr_filter=cfr)
                if reg_results:
                    reg_context = regulatory_corpus_engine.format_regulatory_context(reg_results)

            # Annotate finding with all sources
            if fda_precedents or intl_matches:
                finding.enforcement_match = True
                fda_excerpt = rag_engine.format_enforcement_excerpt(fda_precedents) if fda_precedents else ""
                intl_excerpt = international_enforcement_engine.format_international_excerpt(intl_matches) if intl_matches else ""

                parts = []
                if fda_excerpt:
                    parts.append(fda_excerpt)
                if intl_excerpt:
                    parts.append("── International Enforcement Precedents ──\n" + intl_excerpt)
                if reg_context:
                    parts.append("── Regulatory Basis ──\n" + reg_context)
                finding.enforcement_context = "\n\n".join(parts)

            # ── Severity elevation logic ───────────────────────────────────────
            if cfr and finding.level not in ("L1", "L2"):
                freq = rag_engine.get_cfr_observation_count(cfr)
                multi_agency = len(intl_matches) >= 1  # FDA + at least 1 other agency

                if freq >= _FREQ_CRITICAL:
                    finding.severity = "critical"
                    if not finding.severity_elevated:
                        finding.severity_elevated = True
                        agencies_note = self._multi_agency_note(fda_precedents, intl_matches)
                        prefix = (
                            f"⚠ Severity elevated to critical: {cfr} appears in {freq} "
                            f"FDA enforcement actions{agencies_note}.\n\n"
                        )
                        finding.enforcement_context = prefix + (finding.enforcement_context or "")
                    if cfr not in seen_cfr_l9:
                        seen_cfr_l9.add(cfr)
                        l9_findings.append(self._make_l9_finding(
                            cfr, freq, fda_precedents, intl_matches, "critical"
                        ))

                elif freq >= _FREQ_ELEVATE and not finding.severity_elevated:
                    original = finding.severity
                    elevated = _ELEVATION_MAP.get(finding.severity, finding.severity)
                    # Multi-agency corroboration: elevate one extra level if found internationally too
                    if multi_agency and elevated != "critical":
                        elevated = _ELEVATION_MAP.get(elevated, elevated)
                    if elevated != original:
                        finding.severity = elevated
                        finding.severity_elevated = True
                        agencies_note = self._multi_agency_note(fda_precedents, intl_matches)
                        prefix = (
                            f"⚠ Severity elevated from {original} to {elevated}: "
                            f"{cfr} appears in {freq} FDA enforcement actions{agencies_note}.\n\n"
                        )
                        finding.enforcement_context = prefix + (finding.enforcement_context or "")
                    if cfr not in seen_cfr_l9:
                        seen_cfr_l9.add(cfr)
                        l9_findings.append(self._make_l9_finding(
                            cfr, freq, fda_precedents, intl_matches, elevated
                        ))

                elif multi_agency and not finding.severity_elevated and finding.severity == "low":
                    # Low FDA frequency but confirmed by international agency → bump to medium
                    finding.severity = "medium"
                    finding.severity_elevated = True
                    agencies = list({r['source_agency'] for r in intl_matches})
                    finding.enforcement_context = (
                        f"⚠ Severity elevated to medium: pattern also observed by {', '.join(agencies)}.\n\n"
                        + (finding.enforcement_context or "")
                    )

        if l9_findings:
            logger.info(
                f"Enforcement engine: {len(l9_findings)} L9 findings, "
                f"{sum(1 for f in existing_findings if f.enforcement_match)} findings annotated, "
                f"international={len(international_enforcement_engine.get_agencies_with_data())} agencies loaded"
            )

        return l9_findings

    def _multi_agency_note(self, fda_results: list[dict], intl_results: list[dict]) -> str:
        if not intl_results:
            return ""
        agencies = list({r['source_agency'] for r in intl_results})
        return f" and corroborated by {', '.join(agencies)}"

    def _make_l9_finding(
        self,
        cfr: str,
        freq: int,
        fda_precedents: list[dict],
        intl_matches: list[dict],
        severity: str,
    ) -> FindingResult:
        company = fda_precedents[0]['company'] if fda_precedents else "multiple companies"
        year = fda_precedents[0]['year'] if fda_precedents else ""
        office = fda_precedents[0]['office'] if fda_precedents else "FDA"
        excerpt = fda_precedents[0]['text'][:400] if fda_precedents else ""

        intl_note = ""
        if intl_matches:
            agencies = list({r['source_agency'] for r in intl_matches})
            intl_note = (
                f" This pattern has also been cited in enforcement actions by {', '.join(agencies)}, "
                "indicating it is a globally recognized deficiency."
            )

        fda_excerpt = rag_engine.format_enforcement_excerpt(fda_precedents)
        intl_excerpt = international_enforcement_engine.format_international_excerpt(intl_matches)
        combined_context_parts = []
        if fda_excerpt:
            combined_context_parts.append(fda_excerpt)
        if intl_excerpt:
            combined_context_parts.append("── International ──\n" + intl_excerpt)

        return FindingResult(
            level="L9",
            severity=severity,
            category="enforcement_pattern_match",
            title=f"High-frequency enforcement pattern: {cfr} ({freq} FDA actions)",
            description=(
                f"{cfr} appears in {freq} FDA enforcement actions — placing this in the top "
                f"enforcement risk categories tracked by Clyira's corpus. FDA investigators "
                f"specifically target this deficiency during inspections.{intl_note} "
                f"Recent FDA example: {company} ({office}, {year})."
            ),
            evidence=excerpt,
            regulatory_citation=cfr,
            citation_type="enforcement",
            agency="FDA",
            enforcement_match=True,
            enforcement_context="\n\n".join(combined_context_parts),
            severity_elevated=True,
            confidence_score=0.95,
            validated=True,
        )

    def elevate_severities(
        self, findings: list[FindingResult], enforcement_records: list[dict]
    ) -> list[FindingResult]:
        # Elevation is handled inside run(). Kept for orchestrator compatibility.
        return findings
