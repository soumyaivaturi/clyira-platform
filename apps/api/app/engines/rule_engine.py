"""
Rule Engine — Deterministic structural and compliance checks.
Handles: L1 (Structural), L2 (Doc Control), L4 (ALCOA+), L5 (Data Intelligence),
         L7 (Lifecycle), and structural portions of L11.
"""
import re
import logging
from typing import Optional

from app.engines.types import AssessmentContext, FindingResult
from app.dtap.profile import DTAPProfile

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Executes deterministic rule-based checks.
    Rules are defined in the DTAP profile and executed by category.
    """

    async def run(self, context: AssessmentContext, levels: list[str]) -> list[FindingResult]:
        """Run rule checks for specified levels"""
        findings: list[FindingResult] = []
        profile = context.dtap_profile

        for level in levels:
            level_config = profile.levels.get(level)
            if not level_config or not level_config.enabled:
                continue

            if level_config.engine not in ("rule", "hybrid"):
                continue

            level_findings = await self._run_level(level, level_config.checks, context)
            findings.extend(level_findings)

        return findings

    async def _run_level(self, level: str, checks: list[str], context: AssessmentContext) -> list[FindingResult]:
        """Run all checks for a specific level. Unimplemented checks are queued for LLM fallback."""
        findings = []
        unimplemented = []

        for check_name in checks:
            check_fn = self._get_check_function(level, check_name)
            if check_fn:
                result = check_fn(context)
                if result:
                    findings.extend(result if isinstance(result, list) else [result])
            else:
                unimplemented.append(check_name)

        # Route unimplemented rule checks to LLM
        if unimplemented and context.dtap_profile:
            llm_findings = await self._llm_fallback(level, unimplemented, context)
            findings.extend(llm_findings)

        return findings

    async def _llm_fallback(self, level: str, checks: list[str], context: AssessmentContext) -> list[FindingResult]:
        """Send unimplemented rule checks to the LLM engine."""
        from app.engines.llm_engine import LLMEngine
        from app.core.config import settings
        if not settings.GEMINI_API_KEY:
            return []
        try:
            engine = LLMEngine()
            return await engine.run_checks(level, checks, context)
        except Exception as e:
            logger.warning(f"LLM fallback failed for {level} checks {checks}: {e}")
            return []

    def _get_check_function(self, level: str, check_name: str):
        """Resolve check function by level and name"""
        method_name = f"_check_{level.lower()}_{check_name}"
        return getattr(self, method_name, None)

    # ========== L1: Structural Integrity Checks ==========

    def _check_l1_required_sections_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Verify all required sections exist in the document"""
        findings = []
        profile = ctx.dtap_profile
        doc_text_lower = ctx.document_text.lower()

        for section in profile.required_sections:
            # Check if section header exists (flexible matching)
            patterns = [
                section.lower(),
                section.lower().replace(" ", ""),
                re.escape(section.lower()),
            ]
            found = any(p in doc_text_lower for p in patterns)

            if not found:
                findings.append(FindingResult(
                    level="L1",
                    severity="high",
                    category="missing_section",
                    title=f"Required section missing: {section}",
                    description=f"The required section '{section}' was not found in the document. "
                                f"Per the {profile.document_category} DTAP, this section is mandatory.",
                    evidence=f"Expected section '{section}' not detected in document structure.",
                    regulatory_citation="21 CFR 211.100 — Written procedures required",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.95,
                    validated=True,
                ))

        return findings

    def _check_l1_section_ordering(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Verify sections appear in expected order"""
        findings = []
        profile = ctx.dtap_profile
        if not profile.section_order_matters:
            return findings

        doc_text_lower = ctx.document_text.lower()
        last_pos = -1

        for section in profile.required_sections:
            pos = doc_text_lower.find(section.lower())
            if pos != -1 and pos < last_pos:
                findings.append(FindingResult(
                    level="L1",
                    severity="low",
                    category="section_order",
                    title=f"Section out of expected order: {section}",
                    description=f"The section '{section}' appears before a section that should precede it.",
                    evidence=f"Section found at position {pos}, but previous required section was at {last_pos}.",
                    confidence_score=0.85,
                    validated=True,
                ))
            if pos != -1:
                last_pos = pos

        return findings

    def _check_l1_document_number_format(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check document has a proper document number"""
        # Look for common document number patterns
        patterns = [
            r'[A-Z]{2,5}-\d{3,5}',  # SOP-001, CAPA-2026-0042
            r'[A-Z]{2,5}-[A-Z]{2,5}-\d{3,5}',  # ATM-PRD-112
            r'Document\s*(?:No|Number|#)\s*[:.]?\s*\S+',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text):
                return None

        return FindingResult(
            level="L1",
            severity="medium",
            category="document_number",
            title="Document number not detected",
            description="No standard document numbering format was detected in the document.",
            evidence="Expected format like SOP-001, CAPA-2026-XXXX, or similar identifier.",
            regulatory_citation="21 CFR 211.186 — Master production and control records identification",
            citation_type="traceability",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )

    def _check_l1_version_control_block(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check for version/revision information"""
        patterns = [
            r'(?:version|revision|rev\.?)\s*[:.]?\s*\d',
            r'(?:effective\s+date|eff\.?\s+date)',
            r'revision\s+history',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L1",
            severity="medium",
            category="version_control",
            title="Version control information missing",
            description="No version/revision information or effective date was detected.",
            evidence="Document lacks version number, revision indicator, or effective date block.",
            regulatory_citation="21 CFR 211.100(a) — Written procedures, deviations",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
        )

    def _check_l1_approval_signatures(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check for approval/signature block"""
        patterns = [
            r'(?:approved|authorized)\s+by',
            r'(?:signature|sign|signed)',
            r'(?:author|prepared\s+by|reviewed\s+by|approved\s+by)',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L1",
            severity="high",
            category="approval_signatures",
            title="Approval signatures not detected",
            description="No approval or signature block was found in the document. "
                        "GMP documents require documented approval by appropriate personnel.",
            evidence="No signature indicators (Approved By, Reviewed By, etc.) found.",
            regulatory_citation="21 CFR 211.100(a) — Written procedures shall be drafted, reviewed, and approved",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.90,
            validated=True,
        )

    # ========== L2: Document Control Checks ==========

    def _check_l2_effective_date_present(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check for effective date"""
        patterns = [
            r'effective\s+date\s*[:.]?\s*\d',
            r'effective\s*[:.]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'eff(?:ective)?\.?\s+\d{1,2}\s+\w+\s+\d{4}',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L2",
            severity="medium",
            category="effective_date",
            title="Effective date not specified",
            description="No effective date was found. Documents must have a clear effective date for control purposes.",
            evidence="No date pattern found near 'effective date' indicator.",
            confidence_score=0.85,
            validated=True,
        )

    def _check_l2_review_date_present(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check for next review date"""
        patterns = [
            r'(?:next\s+)?review\s+date',
            r'review\s+(?:due|by)',
            r'periodic\s+review',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L2",
            severity="low",
            category="review_date",
            title="Review date not specified",
            description="No next review date or periodic review schedule was found.",
            evidence="Best practice: documents should specify when the next review is due.",
            confidence_score=0.75,
            validated=True,
        )

    # ========== L4: ALCOA+ Checks ==========

    def _check_l4_alcoa_attributable(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check ALCOA Attributable — who performs and records"""
        patterns = [
            r'(?:performed\s+by|recorded\s+by|operator|analyst)',
            r'(?:initials?|signature)',
            r'(?:responsible\s+(?:person|party|individual))',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L4",
            severity="high",
            category="alcoa_attributable",
            title="ALCOA+ Attributable: Recording attribution missing",
            description="The document does not clearly specify who performs or records activities. "
                        "Data must be attributable to the person who generated it.",
            evidence="No 'performed by', 'recorded by', or signature/initials requirements found.",
            regulatory_citation="FDA Data Integrity Guidance (2018) — Attributable requirement",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
        )

    def _check_l4_alcoa_contemporaneous(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check ALCOA Contemporaneous — recorded at time of activity"""
        patterns = [
            r'(?:record\s+(?:at|during|immediately|at\s+the\s+time))',
            r'(?:real[\s-]?time|contemporaneous)',
            r'(?:date\s+and\s+time|timestamp)',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L4",
            severity="medium",
            category="alcoa_contemporaneous",
            title="ALCOA+ Contemporaneous: Timing requirements unclear",
            description="The document does not specify that records should be made at the time of the activity.",
            evidence="No contemporaneous recording instructions (e.g., 'record at time of', 'real-time') found.",
            regulatory_citation="FDA Data Integrity Guidance — Contemporaneous requirement",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )

    # ========== L7: Lifecycle Checks ==========

    def _check_l7_review_cycle_compliance(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check if document defines review cycle"""
        patterns = [
            r'(?:review(?:ed)?\s+(?:every|annually|biannually|quarterly))',
            r'(?:\d+\s*(?:year|month|day)\s+review)',
            r'(?:periodic\s+review)',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L7",
            severity="low",
            category="review_cycle",
            title="Review cycle not defined",
            description="No periodic review cycle was specified in the document.",
            evidence="Best practice: GMP documents should define review frequency (typically 2-3 years).",
            confidence_score=0.75,
            validated=True,
        )

    def _check_l7_training_requirements_defined(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Check if training requirements are specified"""
        patterns = [
            r'(?:training\s+(?:required|requirement|must|shall))',
            r'(?:read\s+and\s+understand)',
            r'(?:qualified|competency)',
        ]
        for pattern in patterns:
            if re.search(pattern, ctx.document_text, re.IGNORECASE):
                return None

        return FindingResult(
            level="L7",
            severity="medium",
            category="training_requirements",
            title="Training requirements not defined",
            description="The document does not specify training requirements for personnel executing this procedure.",
            evidence="No training, qualification, or competency requirements found.",
            regulatory_citation="21 CFR 211.25 — Personnel qualifications and training",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )
