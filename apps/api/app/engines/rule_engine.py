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

# ──────────────────────────────────────────────────────────────────────────────
# Module-level helpers (shared by universal scanners and domain-specific checks)
# ──────────────────────────────────────────────────────────────────────────────

def _nearest_section(text: str, pos: int, window: int = 400) -> str:
    excerpt = text[max(0, pos - window):pos]
    matches = list(re.finditer(
        r'(?:^|\n)(?:Section\s+)?(\d[\d.]*)\s*[.—–-]\s*([A-Z][^\n]{3,60})',
        excerpt, re.IGNORECASE
    ))
    if matches:
        m = matches[-1]
        return f"Section {m.group(1)} — {m.group(2).strip().rstrip('.')}"
    caps = list(re.finditer(r'\n([A-Z][A-Z\s]{4,50})\n', excerpt))
    if caps:
        return caps[-1].group(1).strip().title()
    return ""


def _extract_sentence(text: str, pos: int) -> str:
    start = max(0, text.rfind('\n', 0, pos) + 1)
    end_nl = text.find('\n', pos)
    end_dot = text.find('.', pos)
    if end_nl == -1 and end_dot == -1:
        end = len(text)
    elif end_nl == -1:
        end = end_dot + 1
    elif end_dot == -1:
        end = end_nl
    else:
        end = min(end_nl, end_dot + 1)
    return text[start:end].strip()[:300]


_VAGUE_TERMS = [
    ("as needed",           "high",   "21 CFR 211.100(a)", True),
    ("if necessary",        "high",   "21 CFR 211.100(a)", True),
    ("when necessary",      "high",   "21 CFR 211.100(a)", True),
    ("where applicable",    "medium", "21 CFR 211.100(a)", False),
    ("if applicable",       "medium", "21 CFR 211.100(a)", False),
    ("as appropriate",      "high",   "21 CFR 211.100(a)", True),
    ("going forward",       "high",   "21 CFR 211.100(a)", True),
    ("on an ongoing basis", "high",   "21 CFR 211.100(a)", True),
    ("acceptable range",    "high",   "21 CFR 211.194(a)(2)", True),
    ("acceptable limit",    "high",   "21 CFR 211.194(a)(2)", True),
    ("acceptable level",    "high",   "21 CFR 211.194(a)(2)", True),
]

_VAGUE_SINGLE = [
    ("appropriate", "medium", "21 CFR 211.100(a)"),
    ("suitable",    "medium", "21 CFR 211.100(a)"),
    ("adequate",    "medium", "21 CFR 211.100(a)"),
    ("sufficient",  "medium", "21 CFR 211.100(a)"),
]

_ALLOWLIST_CONTEXT = re.compile(
    r'(quality unit|adequate oversight|adequately|sufficiently\s+qualified|'
    r'sufficient\s+personnel|appropriate\s+personnel|qualified\s+personnel|'
    r'appropriate\s+training\s+records|appropriate\s+facilities)',
    re.IGNORECASE
)


class RuleEngine:
    """
    Executes deterministic rule-based checks.
    Rules are defined in the DTAP profile and executed by category.
    """

    async def run(self, context: AssessmentContext, levels: list[str]) -> list[FindingResult]:
        """Run rule checks for specified levels. Batches all LLM fallbacks into one call."""
        findings: list[FindingResult] = []
        profile = context.dtap_profile
        unimplemented_by_level: dict[str, list[str]] = {}

        for level in levels:
            level_config = profile.levels.get(level)
            if not level_config or not level_config.enabled:
                continue
            if level_config.engine not in ("rule", "hybrid"):
                continue

            level_findings, unimplemented = self._run_level_sync(level, level_config.checks, context)
            findings.extend(level_findings)

            # Only batch fallback for pure-rule levels — hybrid levels are covered by LLM engine pass
            if unimplemented and level_config.engine == "rule":
                unimplemented_by_level[level] = unimplemented

        # ONE batched LLM call for all unimplemented rule checks across all levels
        if unimplemented_by_level and context.dtap_profile:
            llm_findings = await self._llm_fallback_batched(unimplemented_by_level, context)
            findings.extend(llm_findings)

        # Universal scanners — run once per assessment for all document types
        findings.extend(self._scan_vague_language(context))
        findings.extend(self._scan_should_not_shall(context))

        return findings

    def _run_level_sync(self, level: str, checks: list[str], context: AssessmentContext) -> tuple[list[FindingResult], list[str]]:
        """Run deterministic checks for a level. Returns (findings, unimplemented_check_names)."""
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

        return findings, unimplemented

    async def _llm_fallback_batched(self, unimplemented_by_level: dict[str, list[str]], context: AssessmentContext) -> list[FindingResult]:
        """Send ALL unimplemented rule checks (across all levels) to LLM in ONE batched call."""
        from app.engines.llm_engine import LLMEngine, _llm_available
        if not _llm_available():
            return []
        try:
            engine = LLMEngine()
            return await engine.run_checks_batched(unimplemented_by_level, context)
        except Exception as e:
            logger.warning(f"Batched LLM fallback failed: {e}")
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

    # ========== Universal Scanners (all document types) ==========

    def _scan_vague_language(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Scan for vague, non-specific language that cannot be objectively verified."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        seen_phrases: set = set()

        for phrase, severity, citation, _is_high_risk in _VAGUE_TERMS:
            pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(text):
                key = (phrase, _nearest_section(text, m.start()))
                if key in seen_phrases:
                    continue
                seen_phrases.add(key)
                context_window = text[max(0, m.start() - 80):m.end() + 80]
                if _ALLOWLIST_CONTEXT.search(context_window):
                    continue
                sentence = _extract_sentence(text, m.start())
                section = _nearest_section(text, m.start())
                findings.append(FindingResult(
                    level="L3",
                    severity=severity,
                    category="vague_language",
                    title=f"Vague language: '{phrase}'",
                    description=(
                        f"The text uses the phrase '{phrase}' without defining specific criteria, "
                        f"thresholds, or conditions. In the context: '{sentence[:200]}' — this language "
                        f"does not provide sufficient specificity for an analyst to determine compliance "
                        f"without subjective judgment, and cannot be objectively verified during an inspection."
                    ),
                    evidence=sentence,
                    location=section,
                    regulatory_citation=citation,
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.88,
                    validated=True,
                ))

        seen_words: set = set()
        spec_pattern = re.compile(
            r'(acceptance criteria|specification|limit|result|criteria|shall\s+be|must\s+be|'
            r'not\s+(?:less|more|exceed)|nlt|nmt|pass|fail)',
            re.IGNORECASE
        )
        for word, severity, citation in _VAGUE_SINGLE:
            pattern = re.compile(r'\b' + word + r'\b', re.IGNORECASE)
            for m in pattern.finditer(text):
                sentence = _extract_sentence(text, m.start())
                if not spec_pattern.search(sentence):
                    continue
                key = (word, sentence[:60])
                if key in seen_words:
                    continue
                seen_words.add(key)
                context_window = text[max(0, m.start() - 80):m.end() + 80]
                if _ALLOWLIST_CONTEXT.search(context_window):
                    continue
                section = _nearest_section(text, m.start())
                findings.append(FindingResult(
                    level="L3",
                    severity=severity,
                    category="vague_language",
                    title=f"Vague specification language: '{word}'",
                    description=(
                        f"The acceptance criteria or specification statement uses '{word}' without a "
                        f"numeric limit or defined measurable threshold: '{sentence[:200]}'. "
                        f"An FDA investigator cannot verify compliance against a subjective term."
                    ),
                    evidence=sentence,
                    location=section,
                    regulatory_citation=citation,
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.82,
                    validated=True,
                ))

        return findings

    def _scan_should_not_shall(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Detect 'should' in mandatory procedural sections — must be 'shall'."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        should_pattern = re.compile(r'\b(should)\b(?:\s+\w+){1,5}\b', re.IGNORECASE)
        seen: set = set()

        for m in should_pattern.finditer(text):
            sentence = _extract_sentence(text, m.start())
            context_before = text[max(0, m.start() - 200):m.start()]
            if re.search(r'(purpose|background|reference|guideline|recommend)', context_before, re.IGNORECASE):
                continue
            if not re.search(
                r'(procedure|step|analyst|operator|personnel|staff|responsible|shall|must|require)',
                sentence, re.IGNORECASE
            ):
                continue
            key = sentence[:80]
            if key in seen:
                continue
            seen.add(key)
            section = _nearest_section(text, m.start())
            findings.append(FindingResult(
                level="L2",
                severity="medium",
                category="should_not_shall",
                title="'Should' used instead of 'shall' in mandatory instruction",
                description=(
                    f"The instruction '{sentence[:200]}' uses 'should' instead of 'shall'. "
                    f"In GMP documentation, 'should' creates an aspirational, non-mandatory expectation. "
                    f"Mandatory procedural steps must use 'shall' to be enforceable and auditable."
                ),
                evidence=sentence,
                location=section,
                regulatory_citation="21 CFR 211.100(a)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            ))

        return findings

    # ========== L1: CAPA-Specific Checks ==========

    def _check_l1_capa_id(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must have a unique identifier in the document header."""
        text_top = ctx.document_text[:2000]
        has_id = re.search(
            r'CAPA\s*(?:ID|no|number|#|ref)[:\s]*([A-Z0-9][-A-Z0-9.]{2,20})',
            text_top, re.IGNORECASE
        ) or re.search(r'(?:^|\n)[A-Z]{2,6}-\d{4}-\d{3,6}', text_top)
        if has_id:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="capa_id",
            title="CAPA identifier not found in document header",
            description=(
                "No CAPA identifier was found in the document header. Every CAPA must carry a "
                "unique ID for traceability within the quality management system."
            ),
            evidence="Expected format: CAPA-2026-0042 or 'CAPA ID: [value]'",
            location="Document Header",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l1_action_owners_and_dates(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Every corrective/preventive action must have a named owner and a target due date."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        action_lines = re.findall(r'(?:^|\n)\s*\d+\.\d+\s+.{10,}', text)
        if not action_lines:
            return []

        missing_owner = []
        missing_date = []
        for line in action_lines:
            line = line.strip()
            has_owner = bool(re.search(
                r'(?:owner|responsible|assigned\s+to|accountability|by\s+[A-Z][a-z]+\s+[A-Z])',
                line, re.IGNORECASE
            ))
            has_date = bool(re.search(
                r'(?:due\s*(?:date)?[:\s]*\d|by\s+\d{4}[-/]\d{2}|target\s*date|complete\s+by)',
                line, re.IGNORECASE
            ))
            if not has_owner:
                missing_owner.append(line[:100])
            if not has_date:
                missing_date.append(line[:100])

        if missing_owner:
            findings.append(FindingResult(
                level="L1",
                severity="high",
                category="action_owner_missing",
                title="Corrective/preventive actions missing named responsible person",
                description=(
                    f"The following corrective/preventive actions have no named responsible person: "
                    f"{'; '.join(missing_owner[:3])}. "
                    f"Every CAPA action must assign a specific role or individual as accountable for "
                    f"implementation. Without a named owner, the action cannot be tracked, escalated "
                    f"on overdue status, or verified as complete during an FDA inspection."
                ),
                evidence=missing_owner[0],
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
            ))
        if missing_date:
            findings.append(FindingResult(
                level="L1",
                severity="high",
                category="action_date_missing",
                title="Corrective/preventive actions missing due date",
                description=(
                    f"The following corrective/preventive actions have no defined due date: "
                    f"{'; '.join(missing_date[:3])}. "
                    f"Every CAPA action must carry a target completion date. Without due dates, "
                    f"the CAPA system cannot enforce timely closure or demonstrate that actions "
                    f"were implemented within a reasonable timeframe — a direct FDA 483 observation pattern."
                ),
                evidence=missing_date[0],
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
            ))
        return findings

    # ========== L2: CAPA-Specific Checks ==========

    def _check_l2_unsigned_approvals(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Detect unsigned/blank QA approval blocks — CAPA has not been formally authorized."""
        text = ctx.document_text
        unsigned = re.search(
            r'(?:QA\s*(?:Manager|Director|Approver|Representative)|Approved\s*By|Signature|Authorised\s*By)'
            r'[:\s]*(?:_{3,}|\.{3,}|\[[\s_]*\]|TBD|N/?A)',
            text, re.IGNORECASE
        )
        if not unsigned:
            return []
        sentence_start = max(0, text.rfind('\n', 0, unsigned.start()) + 1)
        excerpt = text[sentence_start:sentence_start + 200].strip()
        return [FindingResult(
            level="L2",
            severity="critical",
            category="unsigned_approval",
            title="QA approval block is unsigned — CAPA not formally authorized",
            description=(
                f"The approval block contains an unsigned signature line: '{unsigned.group(0).strip()}'. "
                f"A CAPA with an unfilled QA approval block has not been formally reviewed or authorised. "
                f"21 CFR 211.192 requires that all investigations and associated corrective actions be "
                f"reviewed and approved by the quality control unit. An unsigned CAPA cannot be considered "
                f"valid or closed, and would be cited immediately during an FDA inspection."
            ),
            evidence=excerpt,
            location=_nearest_section(text, unsigned.start()) or "Approvals",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.97,
            validated=True,
        )]

    # ========== L3: CAPA-Specific Checks (hybrid engine) ==========

    def _check_l3_human_error_root_cause(self, ctx: AssessmentContext) -> list[FindingResult]:
        """'Human error' as terminal root cause without systemic mechanism — top FDA Warning Letter pattern."""
        text = ctx.document_text
        rc_patterns = [
            r'root\s+cause\b[^\n]{0,100}\bhuman\s+error\b',
            r'root\s+cause\b[^\n]{0,100}\b(?:operator|analyst|personnel)\s+error\b',
            r'root\s+cause\s+(?:was\s+)?(?:determined|confirmed|identified|concluded)\s+to\s+be\s+(?:\w+\s+){0,3}human\s+error',
            r'due\s+to\s+human\s+error',
            r'caused\s+by\s+human\s+error',
            r'result\s+of\s+human\s+error',
            r'human\s+error[.\s]*root\s+cause',
        ]
        systemic_indicators = [
            'sop was', 'procedure was', 'training gap', 'ambiguous', 'unclear',
            'not defined', 'workload', 'design flaw', 'systemic', 'root cause of the error',
            'underlying cause', 'contributing factor', 'because the', 'because there', 'because no',
        ]
        for pat in rc_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                sentence_start = max(0, text.rfind('\n', 0, m.start()) + 1)
                sentence = text[sentence_start:sentence_start + 400].strip()
                context_after = text[m.end():m.end() + 600].lower()
                if any(ind in context_after for ind in systemic_indicators):
                    return []
                return [FindingResult(
                    level="L3",
                    severity="critical",
                    category="human_error_root_cause",
                    title="Root cause terminates at 'human error' without systemic mechanism",
                    description=(
                        f"The root cause is stated as 'human error' without identifying the systemic "
                        f"mechanism that caused the error. The text reads: '{sentence[:200]}'. "
                        f"FDA considers 'human error' a terminal attribution, not a root cause — the "
                        f"CAPA must explain WHY the error occurred: SOP ambiguity, workload design, "
                        f"inadequate training design, or environmental factors. A CAPA that does not "
                        f"address the systemic cause cannot prevent recurrence and will be cited as "
                        f"inadequate in a 483 observation or Warning Letter."
                    ),
                    evidence=sentence[:300],
                    location=_nearest_section(text, m.start()),
                    regulatory_citation="21 CFR 211.192",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.95,
                    validated=True,
                    suggestion_draft=(
                        "Replace 'human error' with the specific systemic mechanism identified by "
                        "5-Why or Fishbone analysis — e.g., SOP step ambiguity, excessive manual "
                        "steps, training design gap, or workload pressure — and cite the evidence."
                    ),
                )]
        return []

    def _check_l3_training_only_capa(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Retraining as the only corrective action — explicitly inadequate per FDA CAPA guidance."""
        text = ctx.document_text
        has_retraining = re.search(r'\bre-?train(?:ed|ing)?\b', text, re.IGNORECASE)
        if not has_retraining:
            return []
        systemic_action_patterns = [
            r'SOP\s+(?:revision|update|change)',
            r'procedure\s+(?:revision|update|change)',
            r'process\s+(?:change|redesign|modification)',
            r'engineering\s+control',
            r'\bautomated\b',
            r'system\s+(?:change|update)',
            r'design\s+(?:change|modification)',
            r'error-?proofing',
            r'poka-?yoke',
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in systemic_action_patterns):
            return []
        sentence_start = max(0, text.rfind('\n', 0, has_retraining.start()) + 1)
        sentence = text[sentence_start:sentence_start + 300].strip()
        return [FindingResult(
            level="L3",
            severity="critical",
            category="training_only_capa",
            title="CAPA consists only of retraining — no systemic corrective action identified",
            description=(
                f"The CAPA actions appear to consist primarily of retraining without an identified "
                f"systemic corrective action. FDA CAPA guidance explicitly states that retraining "
                f"alone is not an acceptable CAPA unless the root cause is confirmed to be a "
                f"training design gap (not operator error). The text references: '{sentence[:200]}'. "
                f"A training-only response to a process or system failure does not address the root "
                f"cause and will not prevent recurrence — this pattern is cited in FDA Warning Letters."
            ),
            evidence=sentence[:250],
            location=_nearest_section(text, has_retraining.start()),
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.88,
            validated=True,
            suggestion_draft=(
                "Add a systemic corrective action that addresses the process, SOP, or design "
                "gap that enabled the failure — retraining alone is not acceptable per FDA guidance."
            ),
        )]

    def _check_l3_effectiveness_criteria(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Effectiveness check must have measurable metric, sample size, and pass/fail threshold."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        has_effectiveness = re.search(
            r'effectiveness?\s+(?:check|review|verification|criteria|monitoring)',
            text, re.IGNORECASE
        )
        if not has_effectiveness:
            findings.append(FindingResult(
                level="L3",
                severity="critical",
                category="effectiveness_criteria_absent",
                title="No effectiveness check criteria defined in CAPA",
                description=(
                    "No effectiveness check criteria were found in this CAPA. FDA requires that "
                    "effectiveness criteria be defined prospectively — before CAPA implementation — "
                    "with a specific measurable metric, sample size or observation period, and "
                    "a pass/fail threshold. Absence of effectiveness criteria means there is no "
                    "defined basis for determining whether the CAPA prevented recurrence."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.85,
                validated=True,
                suggestion_draft=(
                    "EFFECTIVENESS CHECK\n"
                    "Metric: [Specific measurable indicator directly tied to root cause elimination]\n"
                    "Sample size / period: [Minimum N consecutive batches / events, minimum X months]\n"
                    "Acceptance criteria: [Zero recurrences / ≤X% frequency / numeric threshold]\n"
                    "Responsible: [Role name]\n"
                    "Failure response: If criterion not met, re-open CAPA and re-evaluate root cause."
                ),
            ))
            return findings

        eff_start = has_effectiveness.start()
        eff_block = text[eff_start:eff_start + 600]
        vague_eff_patterns = [
            r'monitor\s+for\s+\d+\s+(?:months?|weeks?|days?)',
            r'performance\s+(?:improves?|improvement)',
            r'no\s+further\s+(?:OOS|out.of.spec|deviation|failure|error|incident)',
            r'no\s+(?:additional|more)\s+(?:OOS|deviation|failure|recurrence)',
            r'(?:will\s+be\s+)?(?:monitored?|tracked?)\s+(?:going\s+forward|over\s+time|periodically)',
        ]
        vague_eff = any(re.search(p, eff_block, re.IGNORECASE) for p in vague_eff_patterns)
        no_threshold = not re.search(
            r'(?:zero|no\s+recurrence|NMT|NLT|\d+\s*%|\d+\s+(?:consecutive\s+)?(?:batches?|events?|occurrences?))',
            eff_block, re.IGNORECASE
        )
        if vague_eff and no_threshold:
            findings.append(FindingResult(
                level="L3",
                severity="critical",
                category="effectiveness_criteria_vague",
                title="Effectiveness criteria are subjective — no measurable threshold defined",
                description=(
                    f"The effectiveness criteria state: '{eff_block[:200].strip()}' — this is a "
                    f"subjective or non-measurable criterion. FDA requires effectiveness checks to "
                    f"specify (1) a measurable metric tied directly to the root cause, "
                    f"(2) a minimum sample size or observation period, and (3) a defined pass/fail "
                    f"threshold. Statements such as 'no further OOS results', 'performance improves', "
                    f"or 'monitored going forward' do not satisfy this requirement and will be cited "
                    f"as inadequate CAPA effectiveness planning in a 483 observation."
                ),
                evidence=eff_block[:200].strip(),
                location=_nearest_section(text, eff_start),
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
                suggestion_draft=(
                    "EFFECTIVENESS CHECK\n"
                    "Metric: [Specific measurable indicator directly tied to root cause elimination]\n"
                    "Sample size / period: [Minimum N consecutive batches / events, minimum X months]\n"
                    "Acceptance criteria: [Zero recurrences / ≤X% frequency / numeric threshold]\n"
                    "Responsible: [Role name]\n"
                    "Failure response: If criterion not met, re-open CAPA and re-evaluate root cause."
                ),
            ))
        return findings

    def _check_l3_retrospective_capa(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Corrective actions in past tense indicate CAPA was written after actions completed."""
        text = ctx.document_text
        ca_section = re.search(
            r'(?:corrective\s+action|preventive\s+action|CAPA\s+action).*',
            text, re.IGNORECASE | re.DOTALL
        )
        if not ca_section:
            return []
        ca_text = text[ca_section.start():ca_section.start() + 1500]
        past_tense = re.findall(
            r'\b(?:was|were|has\s+been|have\s+been)\s+'
            r'(?:re-?train\w*|issu\w*|implement\w*|complet\w*|conduct\w*|perform\w*|'
            r'updat\w*|revis\w*|sent\w*|distribut\w*|communicat\w*)',
            ca_text, re.IGNORECASE
        )
        if len(past_tense) < 2:
            return []
        return [FindingResult(
            level="L3",
            severity="critical",
            category="retrospective_capa",
            title="CAPA written retrospectively — actions completed before CAPA was formally opened",
            description=(
                f"The corrective and preventive actions are written in past tense "
                f"({', '.join(set(past_tense[:4]))}), indicating these actions were implemented "
                f"before this CAPA was formally written. This is a retrospective CAPA — a critical "
                f"process failure. FDA requires CAPAs to be prospective: each action must be planned, "
                f"assigned, and approved before implementation. A retrospective record provides no "
                f"evidence that actions were approved prior to implementation, due dates were set and "
                f"tracked, or that the actions were appropriate given the root cause at the time of decision."
            ),
            evidence=ca_text[:300].strip(),
            location=_nearest_section(text, ca_section.start()) or "Corrective Actions",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
            suggestion_draft=(
                "Rewrite all corrective and preventive actions in future tense with owner, due date, "
                "and implementation evidence field — then document completion separately once executed."
            ),
        )]

    # ========== L4: CAPA-Specific Checks ==========

    def _check_l4_oos_invalidation_basis(self, ctx: AssessmentContext) -> list[FindingResult]:
        """OOS result invalidated without referenced scientific evidence — data integrity violation risk."""
        text = ctx.document_text
        invalidated = re.search(
            r'\b(?:result\s+was\s+invalidated|OOS\s+(?:result\s+)?invalidated|'
            r'invalidated\s+(?:the\s+)?(?:result|OOS)|result\s+deemed\s+invalid)',
            text, re.IGNORECASE
        )
        if not invalidated:
            return []
        window = text[max(0, invalidated.start() - 300):invalidated.start() + 600]
        has_evidence = bool(re.search(
            r'(?:investigation\s+(?:report\s+)?(?:ID|no|ref|#)\s*[A-Z0-9-]+|'
            r'report\s+(?:ID|no|ref|#)\s*[A-Z0-9-]+|'
            r'attachment\s+\d|annex\s+\d|appendix\s+\d|'
            r'chromatogram|raw\s+data\s+reviewed|laboratory\s+notebook)',
            window, re.IGNORECASE
        ))
        if has_evidence:
            return []
        excerpt = text[invalidated.start():invalidated.start() + 300].strip()
        return [FindingResult(
            level="L4",
            severity="critical",
            category="oos_invalidation_basis",
            title="OOS result invalidated without referenced scientific evidence",
            description=(
                f"The OOS result is stated as invalidated ('{excerpt[:150]}') but no documented "
                f"scientific evidence is referenced to support this conclusion. "
                f"The FDA OOS Guidance (2006) requires that an assignable cause for OOS "
                f"invalidation be conclusively established through documented evidence — "
                f"chromatographic review, witnessed re-preparation, or equivalent — before "
                f"the original result may be discarded. Undocumented OOS invalidations are a "
                f"potential data integrity violation regardless of intent."
            ),
            evidence=excerpt[:250],
            location=_nearest_section(text, invalidated.start()) or "Problem Statement",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.92,
            validated=True,
            suggestion_draft=(
                "Reference the specific investigation report ID, raw data reviewed, and "
                "documented evidence that conclusively established the assignable cause "
                "before the OOS result was invalidated."
            ),
        )]

    def _check_l4_testing_into_compliance(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Batch retested and passed after OOS invalidation without Phase II investigation."""
        text = ctx.document_text
        retest_pass = re.search(
            r'\b(?:re-?test(?:ed|ing)?|repeat\s+test(?:ing)?)\b.{0,150}\b(?:pass(?:ed)?|within\s+spec|met\s+spec)',
            text, re.IGNORECASE | re.DOTALL
        )
        if not retest_pass:
            return []
        has_phase2_doc = bool(re.search(
            r'(?:Phase\s+II\s+investigation\s+(?:report\s+)?(?:ID|no|ref)|'
            r'retesting\s+(?:strategy|plan|protocol|justification)|'
            r'predefined\s+(?:hypothesis|retesting)|'
            r'QA\s+(?:approved|authorised)\s+(?:retest|retesting))',
            text, re.IGNORECASE
        ))
        has_invalidation = bool(re.search(
            r'\b(?:invalidated|deemed\s+invalid|result\s+invalid)',
            text, re.IGNORECASE
        ))
        if not has_invalidation or has_phase2_doc:
            return []
        excerpt = text[retest_pass.start():retest_pass.start() + 300].strip()
        return [FindingResult(
            level="L4",
            severity="critical",
            category="testing_into_compliance",
            title="Batch retested and passed after OOS invalidation — testing into compliance risk",
            description=(
                f"The document states that an OOS result was invalidated and the batch was "
                f"subsequently retested and passed ('{excerpt[:150]}'). No documented Phase II "
                f"investigation, predefined retesting strategy, or QA-approved retesting "
                f"justification is referenced. FDA OOS Guidance (2006) Section IV requires that "
                f"retesting of an OOS batch is only permissible after Phase II investigation "
                f"conclusively identifies an assignable laboratory cause with documented evidence, "
                f"and only under a predefined retesting protocol approved by QA before retesting "
                f"begins. Retesting without this foundation constitutes 'testing into compliance' — "
                f"a data integrity violation cited in FDA Warning Letters."
            ),
            evidence=excerpt[:250],
            location=_nearest_section(text, retest_pass.start()) or "Problem Statement",
            regulatory_citation="21 CFR 211.160(b)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.90,
            validated=True,
            suggestion_draft=(
                "Document the Phase II investigation report ID, the predefined retesting "
                "strategy, and QA authorisation for retesting before referencing the retest result."
            ),
        )]

    # ========== L3/L8: ATM-Specific Checks ==========

    def _check_l3_system_suitability(self, ctx: AssessmentContext) -> list[FindingResult]:
        """SST section with numeric acceptance criteria required for all chromatographic methods."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        if not re.search(r'(?:HPLC|UHPLC|LC-MS|GC\b|chromatograph|column)', text, re.IGNORECASE):
            return []
        has_sst = re.search(r'system\s+suitability|SST\b', text, re.IGNORECASE)
        if not has_sst:
            return [FindingResult(
                level="L3",
                severity="critical",
                category="system_suitability_absent",
                title="System Suitability Testing (SST) section absent from chromatographic method",
                description=(
                    "This is a chromatographic method but no System Suitability Testing (SST) "
                    "section was found. SST is mandatory for all chromatographic GMP methods per "
                    "USP <621> and 21 CFR 211.194(a). System suitability must be demonstrated before "
                    "any sample data is acquired; results from a run where SST was not performed are invalid."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.194(a)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.88,
                validated=True,
                suggestion_draft=(
                    "SYSTEM SUITABILITY\n"
                    "Perform 6 replicate injections of the reference standard solution before sample analysis.\n"
                    "Required parameters and acceptance criteria (derived from validation report [VAL-ID]):\n"
                    "- Tailing factor: NMT [X.X]\n"
                    "- Theoretical plates: NLT [XXXX]\n"
                    "- %RSD peak area (n=6): NMT [X.X]%\n"
                    "- Resolution (drug peak to nearest impurity): NLT [X.X]\n\n"
                    "If SST criteria are not met: do not proceed with sample analysis."
                ),
            )]
        sst_start = has_sst.start()
        sst_block = text[sst_start:sst_start + 600]
        has_numeric = re.search(
            r'(?:NMT|NLT|not\s+more\s+than|not\s+less\s+than|≤|≥|±|\d+\.\d+|\d+\s*%)',
            sst_block, re.IGNORECASE
        )
        has_only_generic = (
            re.search(r'(?:NMT|≤)\s*2\.0', sst_block) and
            re.search(r'(?:NLT|≥)\s*2[,\s]?000', sst_block) and
            not re.search(r'[Vv]alidation|[Dd]erived\s+from', sst_block)
        )
        if not has_numeric:
            findings.append(FindingResult(
                level="L3",
                severity="critical",
                category="system_suitability_no_criteria",
                title="SST section present but missing numeric acceptance criteria",
                description=(
                    f"The System Suitability section was found but does not contain specific numeric "
                    f"acceptance criteria: '{sst_block[:150].strip()}'. SST acceptance criteria must "
                    f"include numeric limits for tailing factor, theoretical plates, %RSD, and resolution "
                    f"derived from the method validation study — not generic compendial defaults."
                ),
                evidence=sst_block[:200].strip(),
                location=_nearest_section(text, sst_start),
                regulatory_citation="USP <621>",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.85,
                validated=True,
            ))
        elif has_only_generic:
            findings.append(FindingResult(
                level="L3",
                severity="high",
                category="system_suitability_generic_limits",
                title="SST uses generic USP <621> defaults instead of method-specific validation limits",
                description=(
                    "The SST acceptance criteria appear to use generic USP <621> compendial defaults "
                    "(tailing NMT 2.0, plates NLT 2000) without deriving method-specific limits from "
                    "the validation study. Generic compendial defaults may permit severely degraded "
                    "column performance outside the validated state."
                ),
                evidence=sst_block[:200].strip(),
                location=_nearest_section(text, sst_start),
                regulatory_citation="USP <621>",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            ))
        return findings

    def _check_l8_validation_declaration(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Analytical method must declare its validation status and cross-reference a validation report."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        has_validation_ref = re.search(
            r'(?:validation\s+report|validation\s+study|validation\s+no|'
            r'verified\s+per\s+USP|suitability\s+verification|VER-|VAL-)',
            text, re.IGNORECASE
        )
        has_compendial = re.search(
            r'(?:USP\s*<\d+>|per\s+USP|compendial\s+method|EP\s+method)',
            text, re.IGNORECASE
        )
        has_validation_status = re.search(
            r'(?:fully\s+validated|validated\s+(?:per|method)|validation\s+status)',
            text, re.IGNORECASE
        )
        if not has_validation_status and not has_validation_ref:
            findings.append(FindingResult(
                level="L8",
                severity="critical",
                category="validation_declaration_absent",
                title="Method does not declare its validation status",
                description=(
                    "The method does not declare its validation status (fully validated, compendial + "
                    "verified, or phase-appropriate). Every GMP analytical method must identify its "
                    "validation basis and cross-reference the validation or suitability verification "
                    "report. A method without a declared validation status cannot be used in a "
                    "GMP-compliant context per 21 CFR 211.194(a)(2)."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.194(a)(2)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.85,
                validated=True,
                suggestion_draft=(
                    "VALIDATION STATUS\n"
                    "This method is: [select one]\n"
                    "[ ] Fully validated per ICH Q2(R2). Validation Report: [Document ID, Revision].\n"
                    "[ ] Compendial method (USP <___>). Suitability verified per USP <1226>. "
                    "Verification Report: [Document ID, Revision].\n"
                    "[ ] Phase-appropriate (clinical development, Phase [X]). Qualification Report: [ID]."
                ),
            ))
        if has_compendial and not has_validation_ref:
            ctx_text = text[max(0, has_compendial.start() - 100):has_compendial.start() + 200]
            findings.append(FindingResult(
                level="L8",
                severity="critical",
                category="compendial_no_verification",
                title="Compendial method cited without suitability verification report",
                description=(
                    f"The method references a compendial procedure ({has_compendial.group(0)}) but does not "
                    f"cite a suitability verification report. Under USP <1226>, compendial methods are "
                    f"not self-validating — a suitability verification demonstrating the method performs "
                    f"acceptably with the specific analyte, matrix, and laboratory equipment is required. "
                    f"'Per USP' without a documented verification report is not acceptable per FDA expectations."
                ),
                evidence=ctx_text.strip()[:200],
                location=_nearest_section(text, has_compendial.start()),
                regulatory_citation="USP <1226> Verification of Compendial Procedures",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.92,
                validated=True,
            ))
        return findings

    def _check_l8_oos_trigger(self, ctx: AssessmentContext) -> list[FindingResult]:
        """OOS result trigger and escalation procedure must be defined in every analytical method."""
        text = ctx.document_text
        if re.search(
            r'(?:out.of.spec|OOS\b|outside.spec|fails?\s+spec|outside\s+(?:the\s+)?limit)',
            text, re.IGNORECASE
        ):
            return []
        return [FindingResult(
            level="L8",
            severity="critical",
            category="oos_trigger_absent",
            title="No OOS result trigger or escalation procedure defined in analytical method",
            description=(
                "No OOS (out-of-specification) result trigger or escalation procedure was found in "
                "this method. FDA OOS Guidance 2006 and 21 CFR 211.194 require that every analytical "
                "method define the analyst's required action when a result falls outside specification — "
                "including notification, sample retention, and initiation of the OOS investigation. "
                "The absence of this provision means an analyst obtaining an OOS result has no "
                "documented procedural basis for the required response."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.86,
            validated=True,
            suggestion_draft=(
                "OOS/OOT RESULT PROCEDURE\n"
                "If any analytical result falls outside the specification limit:\n"
                "1. Do not repeat the test without QA notification.\n"
                "2. Retain all samples, solutions, and raw data.\n"
                "3. Notify QC Supervisor immediately.\n"
                "4. Initiate OOS investigation per SOP-QC-OOS-001 within 24 hours."
            ),
        )]
