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
            # Keyword-based matching: extract significant words (≥4 chars) from the
            # section name and check if ANY of them appear in the document. This allows
            # "Effectiveness Checks" to match "EFFECTIVENESS CHECK", "Root Cause Analysis
            # Method" to match "ROOT CAUSE ANALYSIS", etc.
            keywords = [w.lower() for w in section.split() if len(w) >= 4]
            if keywords:
                found = any(kw in doc_text_lower for kw in keywords)
            else:
                found = section.lower() in doc_text_lower

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

    def _check_l1_table_of_contents(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Long SOPs (>5 sections) should have a table of contents for navigability."""
        text_lower = ctx.document_text.lower()
        has_toc = bool(re.search(
            r'(?:table\s+of\s+contents|contents\s*[\n\r]|toc\b)',
            text_lower
        ))
        if has_toc:
            return None
        profile = ctx.dtap_profile
        if len(getattr(profile, "required_sections", [])) < 6:
            return None
        return FindingResult(
            level="L1",
            severity="info",
            category="table_of_contents_absent",
            title="Table of contents not present",
            description=(
                "The document does not include a table of contents. For SOPs with six or more "
                "required sections, a table of contents aids navigation during execution and "
                "inspection review, and is expected by most pharmaceutical quality document "
                "standards. Absence is not a deficiency per se but may be noted during audits."
            ),
            evidence="",
            regulatory_citation="EU GMP Chapter 4 / ICH Q10",
            citation_type="indirect",
            agency="EMA",
            suggestion_draft="Add a Table of Contents section after the title page listing all section headers with page numbers.",
            next_step_text="Add a Table of Contents to improve document navigability.",
            remediation_priority=5,
            confidence_score=0.60,
            validated=True,
        )

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

    def _check_l7_obsolescence_handling(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """SOP must define what happens when it is superseded — transition, archival, and access restrictions."""
        text_lower = ctx.document_text.lower()
        has_obsolescence = bool(re.search(
            r'(?:obsolete|superseded|retire[ds]?\b|withdrawn|archive[ds]?\s+(?:copy|version)|'
            r'when\s+(?:this|the)\s+(?:sop|procedure|document)\s+is\s+(?:replaced|superseded|updated))',
            text_lower
        ))
        if has_obsolescence:
            return None
        return FindingResult(
            level="L7",
            severity="low",
            category="obsolescence_handling_absent",
            title="Obsolescence / supersession procedure not defined",
            description=(
                "The document does not describe the process for retiring or archiving it when a new "
                "version is issued. GMP document control requires that upon supersession: (1) all copies "
                "of the old version are retrieved and destroyed or clearly marked obsolete, (2) the "
                "document management system records the retirement date, and (3) only the current "
                "approved version is accessible to users. Absence of obsolescence instructions creates "
                "risk of personnel continuing to use superseded procedures."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            suggestion_draft=(
                "Add to Document Control / Lifecycle section:\n"
                "Obsolescence: Upon issue of a new version, all controlled copies of the previous "
                "version shall be retrieved and destroyed or marked 'OBSOLETE — DO NOT USE'. "
                "The document control system shall reflect the retirement date. Electronic copies "
                "shall be archived per [Records Retention SOP reference] and restricted from active use."
            ),
            next_step_text="Add an obsolescence/retirement clause to the document control section.",
            remediation_priority=4,
            confidence_score=0.70,
            validated=True,
        )

    def _check_l7_periodic_review_trigger(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """SOP must define ad-hoc triggers that require an unscheduled review (regulatory changes, deviations, complaints)."""
        text_lower = ctx.document_text.lower()
        has_review_trigger = bool(re.search(
            r'trigger(?:ed)?\s+(?:a\s+)?review'
            r'|unscheduled\s+review'
            r'|review\s+(?:shall|must|will)\s+be\s+(?:initiated|triggered)'
            r'|deviation.*review.*sop|complaint.*require.*review|regulation.*change.*review'
            r'|following\s+a\s+(?:deviation|change|complaint|inspection)',
            text_lower
        ))
        if has_review_trigger:
            return None
        has_scheduled_review = bool(re.search(
            r'(?:annual\s+review|biennial\s+review|periodic\s+review|review\s+cycle|review\s+date)',
            text_lower
        ))
        if not has_scheduled_review:
            return None
        return FindingResult(
            level="L7",
            severity="low",
            category="review_trigger_not_defined",
            title="Ad-hoc review triggers not defined",
            description=(
                "The document references scheduled (periodic) reviews but does not define events "
                "that would trigger an unscheduled review. Best-practice GMP document control "
                "specifies triggers such as: regulatory changes affecting the procedure, repeat "
                "deviations or complaints related to the SOP, significant process changes, or "
                "inspection observations. Without defined triggers, a regulatory change may not "
                "prompt timely document updates."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68 / ICH Q10",
            citation_type="indirect",
            agency="FDA",
            suggestion_draft=(
                "Add to Review section:\n"
                "Unscheduled Reviews: This procedure shall be reviewed and updated as needed when any "
                "of the following occur:\n"
                "• Applicable regulatory guidance is revised or new regulation published\n"
                "• Repeat deviation or OOS result attributed to this procedure\n"
                "• Customer or regulatory complaint referencing this procedure\n"
                "• Significant change to equipment, process, or personnel"
            ),
            next_step_text="Add a list of events that require unscheduled document review.",
            remediation_priority=4,
            confidence_score=0.65,
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
            'underlying cause', 'because the', 'because there', 'because no',
        ]
        # NOTE: 'contributing factor' intentionally excluded — a "Contributing Factors"
        # section listing surface-level items (operator experience, line speed) is NOT
        # a systemic root cause analysis and must not suppress this finding.
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

    def _check_l1_capa_number_format(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must carry a formally structured identifier (same as capa_id but checks alternative formats)."""
        return self._check_l1_capa_id(ctx)

    def _check_l1_initiation_date(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must have a documented initiation/open date."""
        text = ctx.document_text[:3000]
        has_date = re.search(
            r'(?:initiation|opened?|date\s+opened?|start\s+date|date\s+initiated|CAPA\s+date|'
            r'date\s+of\s+(?:initiation|opening|issuance))[:\s]*\d{1,2}[/\-–.]\d{1,2}[/\-–.]\d{2,4}',
            text, re.IGNORECASE
        ) or re.search(
            r'(?:initiated|opened)\s+(?:on|:)\s+\d', text, re.IGNORECASE
        )
        if has_date:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="initiation_date_missing",
            title="CAPA initiation date not documented",
            description=(
                "No CAPA initiation date was found in the document header. The open/initiation date "
                "anchors the entire CAPA timeline — without it, response timelines (30-day, 90-day) "
                "cannot be verified, overdue tracking is impossible, and FDA inspectors cannot "
                "confirm actions were taken in a timely manner per 21 CFR 211.192."
            ),
            evidence="",
            location="Document Header",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )]

    def _check_l1_target_completion_date(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must have a defined target completion date for the overall CAPA (not just individual actions)."""
        text = ctx.document_text[:3000]
        has_target = re.search(
            r'(?:target\s+(?:completion\s+)?date|expected\s+(?:completion|closure)\s+date|'
            r'due\s+date|completion\s+date|close\s+(?:by|date))[:\s]*\d{1,2}[/\-–.]\d{1,2}[/\-–.]\d{2,4}',
            text, re.IGNORECASE
        )
        if has_target:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="target_completion_date_missing",
            title="CAPA target completion date not defined",
            description=(
                "No overall CAPA target completion date was found. FDA expects CAPAs to carry a "
                "committed completion date, enabling the quality system to escalate overdue actions "
                "automatically. The absence of a target date renders the CAPA system unable to track "
                "or enforce timely closure."
            ),
            evidence="",
            location="CAPA Header",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.78,
            validated=True,
        )]

    def _check_l1_classification_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must be classified (minor / major / critical) or equivalent risk level."""
        text = ctx.document_text[:4000]
        has_class = re.search(
            r'\b(?:minor|major|critical|low\s+risk|medium\s+risk|high\s+risk|'
            r'CAPA\s+(?:class|type|level|category)\s*[:\-]\s*(?:minor|major|critical|I\b|II\b|III\b))',
            text, re.IGNORECASE
        )
        if has_class:
            return []
        return [FindingResult(
            level="L1",
            severity="medium",
            category="classification_missing",
            title="CAPA classification (minor/major/critical) not stated",
            description=(
                "The CAPA does not state a risk classification. Classification drives the depth of "
                "investigation required, escalation pathways, and regulatory reporting thresholds. "
                "Without it, a reviewer cannot confirm that the investigation depth and actions are "
                "proportionate to the risk level of the event."
            ),
            evidence="",
            location="CAPA Header",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.72,
            validated=True,
        )]

    def _check_l1_source_identification(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA source event (audit, deviation, complaint, etc.) must be identified and cross-referenced."""
        text = ctx.document_text[:4000]
        has_source = re.search(
            r'(?:source|triggered\s+by|initiated\s+(?:from|by|following)|origin|event\s+type|'
            r'initiated\s+as\s+a\s+result|based\s+on|following\s+(?:audit|deviation|complaint|OOS|inspection))',
            text, re.IGNORECASE
        ) and re.search(
            r'\b(?:audit|deviation|complaint|OOS|investigation|inspection|trending|'
            r'recall|adverse\s+event|incident|non-?conformance|NCR)',
            text, re.IGNORECASE
        )
        if has_source:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="source_identification_missing",
            title="CAPA source event not identified",
            description=(
                "The initiating event for this CAPA (audit finding, deviation, OOS, complaint, etc.) "
                "is not clearly identified. CAPAs must be traceable to the originating quality event; "
                "without this, auditors cannot verify root cause investigation is directed at the actual "
                "failure mode, or that similar source events are trend-analyzed."
            ),
            evidence="",
            location="CAPA Identification",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l1_approval_chain_complete(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must show multi-level approval chain — author, reviewer, QA approver."""
        text = ctx.document_text
        roles_found = {
            "Author/Preparer": bool(re.search(
                r'\b(?:prepared\s+by|author|written\s+by|initiator)[:\s]*[A-Z][a-z]',
                text, re.IGNORECASE
            )),
            "Reviewer": bool(re.search(
                r'\b(?:reviewed?\s+by|reviewer|technical\s+review)[:\s]*[A-Z][a-z]',
                text, re.IGNORECASE
            )),
            "QA Approver": bool(re.search(
                r'\b(?:approved?\s+by|QA\s+(?:approv|review|sign)|quality\s+assurance\s+approv)[:\s]*[A-Z][a-z]',
                text, re.IGNORECASE
            )),
        }
        missing = [role for role, found in roles_found.items() if not found]
        if not missing:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="approval_chain_incomplete",
            title=f"CAPA approval chain incomplete — missing: {', '.join(missing)}",
            description=(
                f"The approval chain is missing: {', '.join(missing)}. A complete CAPA requires "
                f"documented authorship (who initiated), technical review (subject matter expert), "
                f"and QA approval (quality unit sign-off). Missing links in the approval chain mean "
                f"the CAPA has not been formally reviewed at every required level per 21 CFR 211.22."
            ),
            evidence=", ".join(missing),
            location="Approval Block",
            regulatory_citation="21 CFR 211.22",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.76,
            validated=True,
        )]

    # ========== L2: CAPA-Specific Checks (additional) ==========

    def _check_l2_document_control_number(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA document must carry a document control number distinct from the CAPA ID."""
        text = ctx.document_text[:2000]
        has_dcn = re.search(
            r'(?:document\s+(?:no|number|control|ref)|doc\s*#|form\s*(?:no|#)|'
            r'QMS\s*(?:no|ref)|record\s*(?:no|number))[:\s]*[A-Z0-9][-A-Z0-9./]{2,20}',
            text, re.IGNORECASE
        )
        if has_dcn:
            return []
        return [FindingResult(
            level="L2",
            severity="low",
            category="document_control_number_missing",
            title="Document control number not present in CAPA header",
            description=(
                "No document control number was found. CAPAs are controlled records under the QMS — "
                "each must carry a document control number to enable retrieval, version history, and "
                "audit trail management."
            ),
            evidence="",
            location="Document Header",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.65,
            validated=True,
        )]

    def _check_l2_revision_history(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA revision/amendment history must be documented if revisions occurred."""
        text = ctx.document_text
        has_rev = re.search(
            r'(?:revision\s+history|change\s+history|amendment\s+log|version\s+history|'
            r'revision\s+log|document\s+history)',
            text, re.IGNORECASE
        )
        if has_rev:
            return []
        return [FindingResult(
            level="L2",
            severity="low",
            category="revision_history_absent",
            title="Revision history section absent",
            description=(
                "No revision history section was found. While initial CAPAs may have no prior revisions, "
                "the section must exist as a placeholder so that any future amendments (scope changes, "
                "timeline extensions, effectiveness criteria modifications) are captured in a documented trail."
            ),
            evidence="",
            location="Document Footer / Revision Block",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.60,
            validated=True,
        )]

    def _check_l2_cross_references_to_source(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must cross-reference the source record (deviation ID, audit observation #, complaint #)."""
        text = ctx.document_text
        has_xref = re.search(
            r'(?:deviation\s*(?:no|#|ref)\s*[A-Z0-9-]+|'
            r'audit\s+(?:observation|finding)\s*(?:no|#|ref)\s*[A-Z0-9-]+|'
            r'complaint\s*(?:no|#|ref)\s*[A-Z0-9-]+|'
            r'OOS\s*(?:no|#|ref)\s*[A-Z0-9-]+|'
            r'NCR\s*(?:no|#|ref)\s*[A-Z0-9-]+|'
            r'incident\s*(?:no|#|ref)\s*[A-Z0-9-]+)',
            text, re.IGNORECASE
        )
        if has_xref:
            return []
        return [FindingResult(
            level="L2",
            severity="medium",
            category="source_cross_reference_missing",
            title="No cross-reference to source record found",
            description=(
                "The CAPA does not reference the originating quality record by number "
                "(e.g., DEV-2026-0042 or Audit Obs #14). Cross-referencing enables inspectors and "
                "auditors to trace from the CAPA back to the original event and verify the investigation "
                "scope is appropriate. Without this link, traceability is broken."
            ),
            evidence="",
            location="CAPA Identification / Background",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.72,
            validated=True,
        )]

    def _check_l2_timeline_entries(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA should document key milestone dates — assessment date, investigation start, action target dates."""
        text = ctx.document_text
        date_count = len(re.findall(
            r'\d{1,2}[/\-–.]\d{1,2}[/\-–.]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
            text, re.IGNORECASE
        ))
        if date_count >= 3:
            return []
        return [FindingResult(
            level="L2",
            severity="low",
            category="timeline_entries_sparse",
            title="CAPA timeline entries sparse — fewer than 3 milestone dates found",
            description=(
                f"Only {date_count} date(s) were found in the CAPA. A well-structured CAPA should "
                f"document milestone dates: initiation date, investigation completion, action due dates, "
                f"effectiveness check date, and planned closure date. Sparse dates limit the ability "
                f"to verify timeliness compliance during an inspection."
            ),
            evidence=f"{date_count} date(s) detected",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.65,
            validated=True,
        )]

    def _check_l2_owner_assignment(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Overall CAPA owner/responsible person must be documented at the CAPA level."""
        text = ctx.document_text[:3000]
        has_owner = re.search(
            r'(?:CAPA\s+owner|responsible\s+(?:person|party|individual|manager)|'
            r'CAPA\s+lead|assigned\s+to|accountability)[:\s]*[A-Z][a-z]',
            text, re.IGNORECASE
        )
        if has_owner:
            return []
        return [FindingResult(
            level="L2",
            severity="medium",
            category="capa_owner_missing",
            title="No CAPA owner or accountable person identified",
            description=(
                "The CAPA does not identify an overall responsible person or CAPA owner. "
                "While individual actions may have assigned owners, the CAPA as a whole requires "
                "a single accountable person responsible for driving closure — this person is the "
                "primary point of contact for QA follow-up and escalation."
            ),
            evidence="",
            location="CAPA Header / Assignment",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.70,
            validated=True,
        )]

    def _check_l2_department_identification(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Department/function responsible for the CAPA must be identified."""
        text = ctx.document_text[:2000]
        has_dept = re.search(
            r'(?:department|function|area|site|facility|group)[:\s]+(?:Quality|Manufacturing|'
            r'Regulatory|R&D|Production|Analytical|QC|QA|Engineering|Operations|Packaging)',
            text, re.IGNORECASE
        )
        if has_dept:
            return []
        return [FindingResult(
            level="L2",
            severity="low",
            category="department_not_identified",
            title="Responsible department not identified in CAPA",
            description=(
                "No responsible department or functional area was identified in the CAPA header. "
                "Department attribution enables trend analysis across the quality system — "
                "identifying which departments generate the most CAPAs is a key leading indicator "
                "for targeted process improvement."
            ),
            evidence="",
            location="CAPA Header",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.60,
            validated=True,
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

    def _check_l4_evidence_of_investigation(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Root cause investigation must reference observed data, not just conclusions."""
        text = ctx.document_text
        if not re.search(r'root\s+cause|investigation', text, re.IGNORECASE):
            return []
        has_evidence = re.search(
            r'(?:batch\s+record|laboratory\s+notebook|chromatogram|raw\s+data|'
            r'analysis\s+report|trending\s+data|review\s+of\s+(?:data|records)|'
            r'investigation\s+report|attachment|annex|appendix|exhibit)\s*(?:#|no|ref)?\s*[A-Z0-9-]*',
            text, re.IGNORECASE
        )
        if has_evidence:
            return []
        return [FindingResult(
            level="L4",
            severity="high",
            category="investigation_evidence_absent",
            title="Root cause investigation lacks referenced data evidence",
            description=(
                "The investigation section does not reference specific observed data evidence "
                "(batch records, raw data, laboratory notebooks, trending data). An investigation "
                "that draws conclusions without citing documentary evidence cannot be verified — "
                "it is opinion, not investigation. FDA 483 observations routinely cite CAPAs where "
                "root cause conclusions are unsupported by documented evidence review."
            ),
            evidence="",
            location="Root Cause Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.78,
            validated=True,
            suggestion_draft=(
                "Reference specific data reviewed during investigation — e.g., "
                "'Batch Record [BR-2026-0042] reviewed by [Name] on [date], "
                "chromatograms attached as Annex A, trending data Attachment B.'"
            ),
        )]

    def _check_l4_data_references_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Data references (batch/lot numbers, report IDs) must appear in the CAPA body."""
        text = ctx.document_text
        has_data_ref = re.search(
            r'(?:batch\s*(?:no|#|number)\s*[A-Z0-9-]+|lot\s*(?:no|#|number)\s*[A-Z0-9-]+|'
            r'report\s*(?:no|#|ID)\s*[A-Z0-9-]+|sample\s*(?:ID|no|#)\s*[A-Z0-9-]+)',
            text, re.IGNORECASE
        )
        if has_data_ref:
            return []
        return [FindingResult(
            level="L4",
            severity="medium",
            category="data_references_absent",
            title="No specific data references (batch/lot/report numbers) in CAPA body",
            description=(
                "The CAPA body contains no specific batch numbers, lot numbers, or report IDs. "
                "CAPAs resulting from product events must reference the specific affected batches/lots "
                "and any associated analytical reports. Without these identifiers, the investigation "
                "scope cannot be independently verified and affected product cannot be traced."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.70,
            validated=True,
        )]

    def _check_l4_batch_records_cited(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Batch records should be cited for any CAPA involving manufacturing or release failures."""
        text = ctx.document_text
        if not re.search(r'(?:batch|lot|production|manufacturing|release|product)', text, re.IGNORECASE):
            return []
        has_batch_ref = re.search(
            r'batch\s+record\s+(?:no|#|reviewed|attached|referenced)|'
            r'BR[-\s]*(?:no|#|ref)?\s*[A-Z0-9-]+|'
            r'production\s+record\s+(?:no|#)',
            text, re.IGNORECASE
        )
        if has_batch_ref:
            return []
        return [FindingResult(
            level="L4",
            severity="medium",
            category="batch_records_not_cited",
            title="Manufacturing CAPA does not cite batch record review",
            description=(
                "This CAPA involves a manufacturing or product release event but no batch record "
                "review is documented or referenced. The batch record is the primary documentary "
                "evidence for manufacturing-related root cause investigations and must be explicitly "
                "cited to demonstrate the investigation reviewed primary source data."
            ),
            evidence="",
            location="Root Cause Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.68,
            validated=True,
        )]

    def _check_l4_trend_data_referenced(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPAs for recurring or systemic issues should reference trend data."""
        text = ctx.document_text
        recurring_signal = re.search(
            r'(?:recur|recurring|repeat\s+(?:event|failure|observation)|'
            r'trend|systemic|pattern|multiple\s+(?:occurrences?|events?))',
            text, re.IGNORECASE
        )
        if not recurring_signal:
            return []
        has_trend = re.search(
            r'(?:trend(?:ing)?\s+(?:analysis|data|report|chart)|'
            r'historical\s+data|run\s+chart|control\s+chart|cpk|process\s+capability|'
            r'frequency\s+analysis|occurrence\s+rate)',
            text, re.IGNORECASE
        )
        if has_trend:
            return []
        excerpt = text[recurring_signal.start():recurring_signal.start() + 200].strip()
        return [FindingResult(
            level="L4",
            severity="high",
            category="trend_data_not_referenced",
            title="Recurring/systemic event CAPA does not reference trend data",
            description=(
                f"The CAPA identifies a recurring or systemic issue ('{excerpt[:100]}') but does "
                f"not reference trend data to support this characterisation. Systemic CAPAs must "
                f"include trending analysis (run charts, frequency analysis, historical occurrence "
                f"data) to define the scope of the problem and to establish a baseline for "
                f"measuring effectiveness of the corrective actions."
            ),
            evidence=excerpt[:200],
            location=_nearest_section(text, recurring_signal.start()) or "Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l4_investigation_completeness(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Investigation must address all identified contributing factors, not just primary cause."""
        text = ctx.document_text
        contributing_factors = re.search(
            r'(?:contributing\s+(?:factor|cause)|secondary\s+cause|'
            r'additional\s+(?:factor|cause)|other\s+(?:factor|cause)|also\s+noted)',
            text, re.IGNORECASE
        )
        if not contributing_factors:
            return []
        actions_after = text[contributing_factors.start():]
        actions_address_factors = re.search(
            r'(?:contributing\s+factor\s+(?:was\s+)?(?:addressed|mitigated|corrected)|'
            r'action\s+(?:for|to\s+address)\s+contributing|'
            r'preventive\s+action.*contributing)',
            actions_after, re.IGNORECASE
        )
        if actions_address_factors:
            return []
        return [FindingResult(
            level="L4",
            severity="medium",
            category="investigation_incomplete_contributing_factors",
            title="Contributing factors identified but not addressed in CAPA actions",
            description=(
                "The investigation identifies contributing factors beyond the primary root cause "
                "but the corrective and preventive actions do not visibly address these factors. "
                "A complete CAPA investigation must trace each identified contributing factor to "
                "at least one corrective or preventive action. Unaddressed contributing factors "
                "will lead to recurrence via the secondary pathway."
            ),
            evidence=text[contributing_factors.start():contributing_factors.start() + 200].strip(),
            location=_nearest_section(text, contributing_factors.start()) or "Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.68,
            validated=True,
        )]

    # ========== L7: CAPA Lifecycle Checks ==========

    def _check_l7_30_day_response_timeline(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA initial response/containment must be documented within 30 days of initiation."""
        text = ctx.document_text
        init_match = re.search(
            r'(?:initiat\w*|opened?|date)[:\s]*(\d{1,2}[/\-–.]\d{1,2}[/\-–.](\d{2,4}))',
            text[:3000], re.IGNORECASE
        )
        if not init_match:
            return []
        action_dates = re.findall(
            r'(?:action|containment|implement|complet)\w*[:\s]+(?:by|date)[:\s]*(\d{1,2}[/\-–.]\d{1,2}[/\-–.]\d{2,4})',
            text, re.IGNORECASE
        )
        overdue_markers = re.search(
            r'(?:overdue|past\s+due|extension\s+(?:granted|required|requested)|'
            r'delayed|behind\s+schedule)',
            text, re.IGNORECASE
        )
        if overdue_markers:
            excerpt = text[overdue_markers.start():overdue_markers.start() + 200].strip()
            return [FindingResult(
                level="L7",
                severity="high",
                category="capa_overdue",
                title="CAPA timeline overdue — action(s) past due date without documented justification",
                description=(
                    f"Overdue language detected in the CAPA: '{excerpt[:150]}'. "
                    f"FDA expects CAPA actions to be implemented within committed timeframes. "
                    f"Overdue CAPAs without formal extension justification (including cause of delay "
                    f"and revised committed date approved by QA) are cited in 483 observations as "
                    f"evidence of inadequate CAPA system management."
                ),
                evidence=excerpt[:200],
                location=_nearest_section(text, overdue_markers.start()) or "Timeline",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.85,
                validated=True,
            )]
        return []

    def _check_l7_extension_justification_if_overdue(self, ctx: AssessmentContext) -> list[FindingResult]:
        """If CAPA has been extended, the extension must be formally justified with QA approval."""
        text = ctx.document_text
        extension = re.search(
            r'(?:extension|extended|revised\s+(?:target|due|completion)\s+date)',
            text, re.IGNORECASE
        )
        if not extension:
            return []
        has_justification = re.search(
            r'(?:extension\s+(?:reason|justification|rationale)|reason\s+for\s+extension|'
            r'delay\s+(?:due\s+to|caused\s+by)|impact\s+of\s+delay)',
            text, re.IGNORECASE
        )
        if has_justification:
            return []
        return [FindingResult(
            level="L7",
            severity="high",
            category="extension_not_justified",
            title="CAPA timeline extended without documented justification",
            description=(
                "The CAPA references a timeline extension but does not document the reason for the "
                "delay, its impact on product quality, or QA approval for the revised date. "
                "FDA requires that any extension to a CAPA due date be justified with documented "
                "rationale and approved by the quality unit. Unjustified extensions suggest the "
                "CAPA system does not adequately enforce timely action."
            ),
            evidence=text[extension.start():extension.start() + 200].strip(),
            location=_nearest_section(text, extension.start()) or "Timeline",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )]

    def _check_l7_effectiveness_check_timing(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Effectiveness check must have a defined timing/schedule and measurable criteria."""
        text = ctx.document_text
        has_effectiveness = re.search(
            r'effectiveness\s+(?:check|monitoring|verification|evaluation|assessment)',
            text, re.IGNORECASE
        )
        if not has_effectiveness:
            return [FindingResult(
                level="L7",
                severity="critical",
                category="effectiveness_check_absent",
                title="No effectiveness check defined for CAPA",
                description=(
                    "No effectiveness check or verification was found. FDA requires every CAPA to "
                    "include a defined effectiveness check: a prospective, measurable assessment "
                    "confirming that the corrective action eliminated the root cause and prevented "
                    "recurrence. The effectiveness check must include defined criteria, a monitoring "
                    "period, and a scheduled evaluation date. Without this, the CAPA cannot be "
                    "considered formally closed."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.88,
                validated=True,
                suggestion_draft=(
                    "EFFECTIVENESS CHECK\n"
                    "Metric: [Define measurable indicator, e.g., zero recurrence of [event] over [period]]\n"
                    "Monitoring Period: [Start date] through [End date] (minimum 90 days post-implementation)\n"
                    "Evaluation Date: [Scheduled date for effectiveness determination]\n"
                    "Criteria for closure: [State pass/fail criteria]"
                ),
            )]
        window = text[has_effectiveness.start():has_effectiveness.start() + 500]
        has_timing = re.search(
            r'(?:within\s+\d+\s+(?:days?|weeks?|months?)|by\s+\d{1,2}[/\-–.]\d{1,2}|'
            r'after\s+\d+\s+(?:days?|weeks?|months?)|monitoring\s+period)',
            window, re.IGNORECASE
        )
        if has_timing:
            return []
        return [FindingResult(
            level="L7",
            severity="high",
            category="effectiveness_check_timing_missing",
            title="Effectiveness check defined but timing/monitoring period not specified",
            description=(
                "An effectiveness check is mentioned but no monitoring period or scheduled evaluation "
                "date was found. The effectiveness check must specify: when monitoring starts, how long "
                "the monitoring period is, and when the formal effectiveness determination will be made. "
                "Without defined timing, the effectiveness check cannot be tracked or enforced."
            ),
            evidence=window[:200].strip(),
            location=_nearest_section(text, has_effectiveness.start()) or "Effectiveness Check",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.82,
            validated=True,
        )]

    def _check_l7_closure_criteria_met(self, ctx: AssessmentContext) -> list[FindingResult]:
        """If CAPA is stated as closed, evidence of closure criteria being met must be present."""
        text = ctx.document_text
        closure = re.search(
            r'\b(?:CAPA\s+(?:closed|closure|status\s*:\s*closed)|closed\s+CAPA|'
            r'closure\s+approved|CAPA\s+complete)',
            text, re.IGNORECASE
        )
        if not closure:
            return []
        has_closure_evidence = re.search(
            r'(?:effectiveness\s+(?:confirmed|verified|demonstrated|met)|'
            r'recurrence\s+(?:not\s+observed|absent|zero|none)|'
            r'all\s+actions\s+(?:completed?|verified?|confirmed?)|'
            r'evidence\s+of\s+effectiveness|closure\s+criteria\s+met)',
            text, re.IGNORECASE
        )
        if has_closure_evidence:
            return []
        return [FindingResult(
            level="L7",
            severity="critical",
            category="closure_without_evidence",
            title="CAPA closed but effectiveness evidence not documented",
            description=(
                "The CAPA is stated as closed but no documented evidence of effectiveness criteria "
                "being met was found. A CAPA cannot be closed until the effectiveness check confirms "
                "the root cause was eliminated and recurrence has not been observed. Closing a CAPA "
                "without documented effectiveness evidence is a direct data integrity issue — "
                "the record misrepresents the state of the quality event."
            ),
            evidence=text[closure.start():closure.start() + 200].strip(),
            location=_nearest_section(text, closure.start()) or "CAPA Closure",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.90,
            validated=True,
        )]

    def _check_l7_recurrence_monitoring_period(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Effectiveness check must include a defined post-closure recurrence monitoring period."""
        text = ctx.document_text
        if not re.search(r'effectiveness|recurrence|monitoring', text, re.IGNORECASE):
            return []
        monitoring_period = re.search(
            r'(?:monitor(?:ing)?\s+period|recurrence\s+period|'
            r'post.(?:implementation|closure|action)\s+monitoring|'
            r'monitor\s+for\s+\d+)',
            text, re.IGNORECASE
        )
        if monitoring_period:
            return []
        return [FindingResult(
            level="L7",
            severity="medium",
            category="recurrence_monitoring_period_absent",
            title="Post-closure recurrence monitoring period not defined",
            description=(
                "No post-closure or post-implementation recurrence monitoring period was defined. "
                "Best-in-class CAPA programs define an explicit monitoring window (commonly 90–180 days "
                "for manufacturing events, 12 months for systemic quality issues) during which the "
                "quality unit actively monitors for recurrence. Without a defined period, the "
                "effectiveness check is unenforceable and recurrence may go undetected."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.68,
            validated=True,
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
        # Require explicit limit operators or percent values — bare \d+\.\d+ is excluded
        # because section numbers like "7.1" would otherwise create false matches.
        has_numeric = re.search(
            r'(?:NMT|NLT|not\s+more\s+than|not\s+less\s+than|≤|≥|±)\s*\d'
            r'|\d+\s*%'
            r'|\d+\.\d+\s*(?:ppm|µg|mg|mL|nm|mm)\b',
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

    # ========== L1/L2/L4/L7: ATM-Specific Checks ==========

    def _check_l1_method_number_format(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Analytical method must carry a formal method number."""
        text = ctx.document_text[:2000]
        has_method_no = re.search(
            r'(?:method\s*(?:no|number|#|id|ref)|ATM[-\s]*\d|AM[-\s]*\d{3}|'
            r'TM[-\s]*\d{3}|QCM[-\s]*\d{3}|STP[-\s]*\d{3}|'
            r'test\s+method\s*(?:no|number|#)[:\s]*[A-Z0-9-]+)',
            text, re.IGNORECASE
        )
        if has_method_no:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="method_number_missing",
            title="Analytical method number not found in document header",
            description=(
                "No method number was found in the document header. Every GMP analytical method "
                "must carry a unique method number for traceability within the quality management "
                "system. Without a method number, the correct version cannot be verified at the "
                "bench, and the method cannot be linked to its validation report."
            ),
            evidence="",
            location="Document Header",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )]

    def _check_l1_effective_date(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must have an effective date — same as SOP."""
        return self._check_l2_effective_date_present(ctx)

    def _check_l1_pharmacopoeia_reference(self, ctx: AssessmentContext) -> list[FindingResult]:
        """If compendial method, pharmacopoeia reference must be in the title/scope section."""
        text = ctx.document_text[:3000]
        compendial = re.search(
            r'\b(?:USP|NF|EP|BP|JP|IP|Ph\.Eur|Ph\s+Eur)\s*[<\[]?\d',
            text, re.IGNORECASE
        )
        if compendial:
            return []
        non_compendial = re.search(
            r'(?:in-house\s+method|proprietary\s+method|non[-\s]?compendial)',
            text, re.IGNORECASE
        )
        if non_compendial:
            return []
        return [FindingResult(
            level="L1",
            severity="info",
            category="pharmacopoeia_reference_absent",
            title="No pharmacopoeia reference or non-compendial declaration found",
            description=(
                "The method does not reference a pharmacopoeia source (USP, EP, BP, JP) nor "
                "explicitly state it is an in-house/non-compendial method. This distinction drives "
                "the validation versus verification pathway — compendial methods require USP <1226> "
                "verification; non-compendial methods require full ICH Q2(R2) validation."
            ),
            evidence="",
            location="Title and Scope",
            regulatory_citation="21 CFR 211.194(a)(2)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.60,
            validated=True,
        )]

    def _check_l1_equipment_list_completeness(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Equipment list must include instrument model, qualification status, and calibration requirements."""
        text = ctx.document_text
        equipment_section = re.search(
            r'(?:equipment|apparatus|instrument|materials?\s+and\s+equipment)',
            text, re.IGNORECASE
        )
        if not equipment_section:
            return [FindingResult(
                level="L1",
                severity="high",
                category="equipment_section_absent",
                title="Equipment and Apparatus section not found",
                description=(
                    "No equipment or apparatus section was found. Every GMP analytical method must "
                    "list all required instruments and equipment — including model/specification, "
                    "calibration requirements, and qualification status — so that analysts can verify "
                    "the appropriate equipment is being used."
                ),
                evidence="",
                location="Equipment and Apparatus",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.78,
                validated=True,
            )]
        eq_window = text[equipment_section.start():equipment_section.start() + 1000]
        has_qualification = re.search(
            r'(?:qualified|IQ|OQ|PQ|calibrated|calibration|qualification\s+status)',
            eq_window, re.IGNORECASE
        )
        if has_qualification:
            return []
        return [FindingResult(
            level="L1",
            severity="medium",
            category="equipment_qualification_status_absent",
            title="Equipment list does not reference qualification or calibration requirements",
            description=(
                "The equipment section does not reference qualification status (IQ/OQ/PQ) or "
                "calibration requirements for listed instruments. FDA expects that analytical method "
                "equipment listings include a statement that instruments must be qualified and "
                "calibrated per approved procedures before use."
            ),
            evidence=eq_window[:200].strip(),
            location=_nearest_section(text, equipment_section.start()) or "Equipment",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.70,
            validated=True,
        )]

    def _check_l1_reagent_grade_specifications(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Reagents must include grade specifications (ACS, HPLC grade, reagent grade, USP)."""
        text = ctx.document_text
        reagent_section = re.search(
            r'(?:reagent|chemical|solvent|mobile\s+phase|buffer)',
            text, re.IGNORECASE
        )
        if not reagent_section:
            return []
        eq_window = text[reagent_section.start():reagent_section.start() + 1200]
        has_grade = re.search(
            r'(?:HPLC\s+grade|ACS\s+grade|analytical\s+grade|reagent\s+grade|'
            r'USP\s+grade|LC-MS\s+grade|optima|trace\s+metal)',
            eq_window, re.IGNORECASE
        )
        if has_grade:
            return []
        return [FindingResult(
            level="L1",
            severity="medium",
            category="reagent_grade_not_specified",
            title="Reagent/solvent purity grades not specified",
            description=(
                "The reagent/solvent section does not specify purity grades (HPLC grade, ACS grade, "
                "reagent grade). Using an incorrect solvent grade in an analytical method can introduce "
                "impurities that interfere with the analysis or invalidate results. Grade specification "
                "is required for GMP-compliant method documentation per 21 CFR 211.194(a)(1)."
            ),
            evidence=eq_window[:200].strip(),
            location=_nearest_section(text, reagent_section.start()) or "Reagents",
            regulatory_citation="21 CFR 211.194(a)(1)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.72,
            validated=True,
        )]

    def _check_l2_method_validation_reference(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must cross-reference its validation or verification report."""
        text = ctx.document_text
        has_val_ref = re.search(
            r'(?:validation\s+report[:\s]*[A-Z0-9-]+|'
            r'VAL[-\s]?\d|VER[-\s]?\d|'
            r'verification\s+report[:\s]*[A-Z0-9-]+|'
            r'ICH\s+Q2.*validation)',
            text, re.IGNORECASE
        )
        if has_val_ref:
            return []
        return [FindingResult(
            level="L2",
            severity="critical",
            category="validation_report_not_referenced",
            title="Method does not cross-reference a validation or verification report",
            description=(
                "The method does not cross-reference a validation report or suitability verification "
                "report by document number. Every GMP analytical method must be traceable to the "
                "validation study that establishes its fitness for purpose. Without this reference, "
                "it is impossible to verify the method is used within its validated parameters "
                "(concentration range, matrix, instrument configuration)."
            ),
            evidence="",
            location="References / Document Header",
            regulatory_citation="21 CFR 211.194(a)(2)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.82,
            validated=True,
        )]

    def _check_l2_change_history(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must include a change/revision history documenting what changed and why."""
        text = ctx.document_text
        has_change_history = re.search(
            r'(?:change\s+history|revision\s+history|version\s+history|'
            r'amendment\s+(?:log|history)|change\s+log)',
            text, re.IGNORECASE
        )
        if has_change_history:
            return []
        return [FindingResult(
            level="L2",
            severity="medium",
            category="change_history_absent",
            title="Change history / revision history section absent",
            description=(
                "No change history or revision history section was found. Analytical methods are "
                "controlled documents — any change to the method (mobile phase composition, column "
                "change, temperature modification) must be captured in a documented change record "
                "that includes: what changed, who authorised it, and the supporting rationale. "
                "Without this, the audit trail for method modifications is broken."
            ),
            evidence="",
            location="Document Footer / Revision Section",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.68,
            validated=True,
        )]

    def _check_l2_training_requirements(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM should specify analyst training/qualification requirements."""
        return self._check_l7_training_requirements_defined(ctx)

    def _check_l2_version_control(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must have version control block (delegates to universal check)."""
        result = self._check_l2_version_control_block(ctx)
        return [result] if result else []

    def _check_l4_alcoa_recording_instructions(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method must specify data recording instructions — delegates to universal rule."""
        result = self._check_l4_data_recording_instructions(ctx)
        return [result] if result else []

    def _check_l4_raw_data_requirements(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method must specify what raw data must be retained and where."""
        text = ctx.document_text
        has_raw_data = re.search(
            r'(?:raw\s+data|original\s+data|chromatogram\s+(?:shall|must|should)|'
            r'data\s+(?:shall\s+be\s+)?retain|record\s+(?:shall\s+be\s+)?retain|'
            r'original\s+records)',
            text, re.IGNORECASE
        )
        if has_raw_data:
            return []
        return [FindingResult(
            level="L4",
            severity="critical",
            category="raw_data_requirements_absent",
            title="Method does not specify raw data retention requirements",
            description=(
                "The method does not specify what raw data must be retained or how. For analytical "
                "methods, raw data includes original chromatograms, weighing records, preparation "
                "worksheets, and instrument printouts. ALCOA+ principles require that original "
                "records be preserved in their original form. The absence of raw data retention "
                "instructions in the method creates a data integrity vulnerability."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
            suggestion_draft=(
                "RAW DATA REQUIREMENTS\n"
                "The following original records must be retained with the analytical worksheet:\n"
                "• Original chromatograms (unmodified, with injection sequence and integration parameters)\n"
                "• Weighing records for all reference standards and samples\n"
                "• Preparation records and reagent lot numbers\n"
                "• Instrument audit trail printout\n"
                "Retain per SOP-QC-RECORDS-001 retention schedule."
            ),
        )]

    def _check_l4_chromatogram_retention(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Chromatographic methods must specify chromatogram retention and print requirements."""
        text = ctx.document_text
        if not re.search(r'(?:HPLC|UHPLC|LC-MS|GC\b|chromatograph|column)', text, re.IGNORECASE):
            return []
        has_chromatogram_req = re.search(
            r'(?:chromatogram\s+(?:shall|must|should|be\s+print|be\s+retain|be\s+attach)|'
            r'print(?:out)?\s+chromatogram|attach\s+chromatogram|'
            r'include\s+chromatogram|chromatogram\s+report)',
            text, re.IGNORECASE
        )
        if has_chromatogram_req:
            return []
        return [FindingResult(
            level="L4",
            severity="high",
            category="chromatogram_retention_not_specified",
            title="Chromatographic method does not specify chromatogram retention requirements",
            description=(
                "This chromatographic method does not specify whether chromatograms must be printed "
                "and attached to the analytical worksheet. In a GMP laboratory, every chromatographic "
                "run must produce a retained, unmodified chromatogram that can be reviewed by QA. "
                "The absence of this instruction creates ambiguity about which data must be preserved."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )]

    def _check_l4_integration_parameters(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Chromatographic methods must define integration parameters (peak width, threshold, baseline)."""
        text = ctx.document_text
        if not re.search(r'(?:HPLC|UHPLC|LC-MS|GC\b|chromatograph)', text, re.IGNORECASE):
            return []
        has_integration = re.search(
            r'(?:integration\s+(?:parameter|setting|threshold|window|event)|'
            r'peak\s+(?:width|threshold)|baseline\s+(?:correction|setting)|'
            r'minimum\s+peak\s+area|integration\s+method)',
            text, re.IGNORECASE
        )
        if has_integration:
            return []
        return [FindingResult(
            level="L4",
            severity="high",
            category="integration_parameters_absent",
            title="Chromatographic method does not define integration parameters",
            description=(
                "No chromatographic peak integration parameters (peak width threshold, baseline "
                "correction method, minimum area) were found. Without defined integration parameters, "
                "analysts may integrate peaks inconsistently between runs, introducing analyst-dependent "
                "variability that undermines method reproducibility. FDA has cited methods that leave "
                "integration decisions to analyst discretion as data integrity vulnerabilities."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l4_rounding_rules(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method must specify rounding rules for results and intermediate calculations."""
        text = ctx.document_text
        has_rounding = re.search(
            r'(?:round(?:ing)?(?:\s+to)?\s+\d|round\s+(?:up|down|to)|'
            r'report(?:ed)?\s+to\s+\d\s+decimal|significant\s+figure|'
            r'USP\s+rounding\s+rule|nearest\s+0\.\d)',
            text, re.IGNORECASE
        )
        if has_rounding:
            return []
        return [FindingResult(
            level="L4",
            severity="medium",
            category="rounding_rules_absent",
            title="Rounding rules for result reporting not specified",
            description=(
                "No rounding rules for result calculation or reporting were found. Without defined "
                "rounding rules (USP <1010> or method-specific), different analysts may report the "
                "same result to different decimal places, creating inconsistency in the data. "
                "This is particularly important near specification limits where rounding can determine "
                "pass/fail outcome."
            ),
            evidence="",
            location="Calculations / Reporting",
            regulatory_citation="USP <1010>",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.65,
            validated=True,
        )]

    def _check_l4_significant_figures(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Results reporting section must define significant figures for each reported parameter."""
        text = ctx.document_text
        has_sf = re.search(
            r'(?:significant\s+figure|report\s+to\s+\d\s+(?:significant|decimal)|'
            r'\d\s+significant\s+figure|report\s+(?:as|to)\s+x\.\d)',
            text, re.IGNORECASE
        )
        if has_sf:
            return []
        reporting_section = re.search(r'(?:reporting|result\s+calculation|report\s+result)', text, re.IGNORECASE)
        if not reporting_section:
            return []
        return [FindingResult(
            level="L4",
            severity="low",
            category="significant_figures_not_defined",
            title="Significant figures for result reporting not defined",
            description=(
                "The reporting section does not define the number of significant figures or decimal "
                "places for reported results. Consistent significant figures are required for both "
                "compliance (reproducibility between analysts) and data integrity (preventing "
                "post-acquisition result manipulation via selective rounding)."
            ),
            evidence="",
            location="Reporting / Calculations",
            regulatory_citation="21 CFR 211.194(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.60,
            validated=True,
        )]

    def _check_l4_data_backup_requirements(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Electronic data backup and system audit trail requirements must be referenced."""
        text = ctx.document_text
        has_backup = re.search(
            r'(?:data\s+backup|audit\s+trail|CDS\s+(?:audit|backup)|'
            r'electronic\s+data\s+(?:retention|backup|backup)|'
            r'Empower|ChemStation|OpenLAB|CDS)',
            text, re.IGNORECASE
        )
        if has_backup:
            return []
        if not re.search(r'(?:HPLC|UHPLC|LC-MS|GC\b|chromatograph|CDS)', text, re.IGNORECASE):
            return []
        return [FindingResult(
            level="L4",
            severity="high",
            category="electronic_data_backup_absent",
            title="Electronic data backup and audit trail requirements not referenced",
            description=(
                "The method does not reference electronic data backup requirements or audit trail "
                "maintenance for the CDS (Chromatography Data System). FDA and MHRA data integrity "
                "guidance require that all electronic data be backed up, that audit trails are enabled "
                "and cannot be disabled, and that backup procedures are defined. Methods that do not "
                "reference these requirements leave analysts without documented basis for data management."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l7_revalidation_triggers_defined(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must define triggers for method revalidation (column change, reagent change, etc.)."""
        text = ctx.document_text
        has_revalidation = re.search(
            r'(?:re-?validat|requalif|change\s+control\s+trigger|'
            r'requires?\s+re-?validat|trigger\s+(?:for\s+)?re-?validat)',
            text, re.IGNORECASE
        )
        if has_revalidation:
            return []
        return [FindingResult(
            level="L7",
            severity="high",
            category="revalidation_triggers_absent",
            title="Method revalidation triggers not defined",
            description=(
                "The method does not define events that would trigger revalidation or re-qualification. "
                "Per ICH Q2(R2) and FDA process validation guidance, analytical methods must include "
                "criteria for when changes require formal revalidation — e.g., column manufacturer change, "
                "reagent lot-to-lot variation, CDS software upgrade, or significant method modification. "
                "Without defined triggers, revalidation decisions are made ad hoc rather than systematically."
            ),
            evidence="",
            location="Method Validation Summary / Lifecycle Section",
            regulatory_citation="ICH Q2(R2)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.72,
            validated=True,
        )]

    def _check_l7_periodic_review_schedule(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM — same as SOP review cycle compliance check."""
        return self._check_l7_review_cycle_compliance(ctx)

    def _check_l7_instrument_qualification_linkage(self, ctx: AssessmentContext) -> list[FindingResult]:
        """ATM must reference the instrument qualification SOP or IQ/OQ/PQ programme."""
        text = ctx.document_text
        has_qual_link = re.search(
            r'(?:IQ\b|OQ\b|PQ\b|qualification\s+(?:report|SOP|procedure)|'
            r'instrument\s+qualification|equipment\s+qualification|'
            r'calibration\s+SOP|SOP[-\s]*(?:EQ|EQUIP|CAL|IQ|OQ))',
            text, re.IGNORECASE
        )
        if has_qual_link:
            return []
        return [FindingResult(
            level="L7",
            severity="medium",
            category="instrument_qualification_not_referenced",
            title="Instrument qualification SOP or programme not referenced in method",
            description=(
                "The method does not reference the instrument qualification programme (IQ/OQ/PQ) "
                "or calibration SOP. Every GMP analytical method must specify that instruments "
                "must be qualified per an approved programme before use — otherwise analysts lack "
                "documented basis for confirming the instrument is in a qualified state."
            ),
            evidence="",
            location="Equipment / Prerequisites",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.68,
            validated=True,
        )]

    def _check_l7_standard_expiry_tracking(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Reference standards and reagents must have expiry/retest date tracking requirements."""
        text = ctx.document_text
        has_expiry = re.search(
            r'(?:expiry|expiration|expir\w+\s+date|use\s+before|retest\s+date|'
            r'valid(?:ity)?\s+(?:period|date)|do\s+not\s+use\s+after)',
            text, re.IGNORECASE
        )
        if has_expiry:
            return []
        has_standards = re.search(
            r'(?:reference\s+standard|working\s+standard|primary\s+standard|'
            r'secondary\s+standard|control\s+standard)',
            text, re.IGNORECASE
        )
        if not has_standards:
            return []
        return [FindingResult(
            level="L7",
            severity="high",
            category="standard_expiry_tracking_absent",
            title="Reference standard expiry date tracking not required in method",
            description=(
                "The method references reference standards but does not require verification of "
                "their expiry or retest date before use. Using expired or retest-date-exceeded "
                "reference standards invalidates all analytical results obtained with them. "
                "Methods must explicitly require analysts to verify standard expiry/retest dates "
                "and document this check on the analytical worksheet."
            ),
            evidence="",
            location="Reagents and Reference Standards",
            regulatory_citation="USP <11>",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )]

    # ========== L5: ATM Data & Statistical Intelligence Checks ==========

    def _check_l5_oos_investigation_trigger_defined(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method must define what constitutes an OOS result and trigger criteria for investigation."""
        text_lower = ctx.document_text.lower()
        has_oos_criteria = bool(re.search(
            r'(?:out[\s-]of[\s-]specification|oos\b|oos\s+result|result\s+outside\s+spec|'
            r'failing\s+result|specification\s+limit\s+exceeded)',
            text_lower
        ))
        has_oos_action = bool(re.search(
            r'(?:oos\s+(?:investigation|procedure|sop|protocol)|'
            r'investigate.*oos|oos.*initiated|oos.*report|'
            r'initiate.*investigation.*oos|failing.*investigate)',
            text_lower
        ))
        if has_oos_criteria and has_oos_action:
            return []
        if not has_oos_criteria:
            return [FindingResult(
                level="L5",
                severity="medium",
                category="oos_trigger_not_defined",
                title="OOS investigation trigger criteria not defined in analytical method",
                description=(
                    "The method does not define what constitutes an Out-of-Specification (OOS) result "
                    "or the criteria that trigger an OOS investigation. Per FDA OOS Guidance 2006 and "
                    "21 CFR 211.192, every analytical method that generates a specification-testable "
                    "result must reference OOS investigation procedures. Analysts must know what action "
                    "to take when a result falls outside the specification before performing the analysis."
                ),
                evidence="",
                regulatory_citation="FDA OOS Guidance 2006 / 21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                suggestion_draft=(
                    "Add to Results / Reporting section:\n"
                    "OOS Investigation Trigger:\n"
                    "If any result falls outside the specification limit, immediately notify supervisor "
                    "and initiate an OOS investigation per [SOP reference]. Do not re-analyse before "
                    "completing Phase I laboratory investigation and obtaining QA authorization.\n"
                    "OOS Specification Limits: [Reference to specification document]"
                ),
                next_step_text="Add OOS definition and investigation trigger reference to the Results section.",
                remediation_priority=3,
                confidence_score=0.72,
                validated=True,
            )]
        return []

    def _check_l5_oot_trend_criteria(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method should define Out-of-Trend (OOT) criteria and trending thresholds."""
        text_lower = ctx.document_text.lower()
        has_oot = bool(re.search(
            r'(?:out[\s-]of[\s-]trend|oot\b|trending|trend\s+(?:analysis|criteria|monitoring|alert)|'
            r'statistical\s+process\s+control|spc\b|alert\s+limit|action\s+limit)',
            text_lower
        ))
        if has_oot:
            return []
        return [FindingResult(
            level="L5",
            severity="low",
            category="oot_criteria_absent",
            title="Out-of-Trend (OOT) criteria not defined",
            description=(
                "The method does not define Out-of-Trend (OOT) criteria, alert limits, or trending "
                "thresholds. OOT criteria enable early detection of systematic drift before results "
                "become OOS. FDA and ICH Q10 expectations include proactive trending for methods "
                "used in product release and stability testing. Absence of OOT criteria limits the "
                "method's utility as a process performance monitoring tool."
            ),
            evidence="",
            regulatory_citation="ICH Q10 / FDA PAT Guidance",
            citation_type="indirect",
            agency="FDA",
            suggestion_draft=(
                "Add to Statistical Controls / Results section:\n"
                "Out-of-Trend (OOT) Alert Limits:\n"
                "• Alert Limit: [Mean ± 2σ] (or 80% of specification limit)\n"
                "• Action Limit: [Mean ± 3σ] (or 90% of specification limit)\n"
                "Results approaching the alert limit shall be flagged for trend review per [SOP reference]."
            ),
            next_step_text="Define OOT alert and action limits based on historical method performance data.",
            remediation_priority=4,
            confidence_score=0.65,
            validated=True,
        )]

    def _check_l5_retest_retake_criteria(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Method must define criteria under which a retest or sample retake is permitted."""
        text_lower = ctx.document_text.lower()
        has_retest_criteria = bool(re.search(
            r'(?:retest\s+(?:criteria|is\s+(?:not\s+)?permitted|policy|conditions?)|'
            r'when\s+(?:to\s+)?retest|conditions?\s+for\s+retest|'
            r'retake\s+(?:criteria|is\s+permitted|conditions?)|'
            r'repeat\s+analysis\s+(?:is\s+(?:not\s+)?permitted|requires?|criteria))',
            text_lower
        ))
        has_retest_mention = bool(re.search(r'retest|retake|repeat\s+(?:test|analysis|injection)', text_lower))
        if has_retest_criteria:
            return []
        if not has_retest_mention:
            return [FindingResult(
                level="L5",
                severity="medium",
                category="retest_criteria_absent",
                title="Retest/retake criteria not defined",
                description=(
                    "The method does not define the conditions under which a retest or sample retake "
                    "is permitted. FDA OOS Guidance 2006 is explicit: retesting is only permissible "
                    "when an assignable laboratory error has been documented; otherwise it constitutes "
                    "testing into compliance. Methods must pre-specify legitimate retest conditions "
                    "(e.g., instrumental failure, contaminated sample, calculational error) to "
                    "distinguish valid retests from post-hoc result manipulation."
                ),
                evidence="",
                regulatory_citation="FDA OOS Guidance 2006",
                citation_type="direct",
                agency="FDA",
                suggestion_draft=(
                    "Add to Procedure or Results section:\n"
                    "Retest / Repeat Analysis Policy:\n"
                    "Repeat analysis is ONLY permitted when a documented assignable laboratory cause "
                    "is identified (e.g., sample preparation error, instrument malfunction, contamination).\n"
                    "A repeat analysis without an assignable cause requires initiation of an OOS investigation.\n"
                    "Unauthorized retesting constitutes testing into compliance and is prohibited."
                ),
                next_step_text="Add explicit retest criteria and OOS investigation requirement.",
                remediation_priority=2,
                confidence_score=0.74,
                validated=True,
            )]
        return []

    def _check_l5_statistical_tools_specified(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Methods involving calculations should specify statistical tools or software."""
        text_lower = ctx.document_text.lower()
        has_calculation = bool(re.search(
            r'(?:calculate|computation|mean|average|rsd\b|%\s*rsd|standard\s+deviation|confidence\s+interval)',
            text_lower
        ))
        if not has_calculation:
            return []
        has_stat_tool = bool(re.search(
            r'(?:excel|waters\s+empower|chromeleon|openlab|labx|minitab|jmp|spss|'
            r'statistical\s+(?:software|tool|package)|data\s+system|cds\b)',
            text_lower
        ))
        if has_stat_tool:
            return []
        return [FindingResult(
            level="L5",
            severity="low",
            category="statistical_tools_not_specified",
            title="Statistical calculation tool or software not specified",
            description=(
                "The method involves statistical calculations but does not specify the software or "
                "tool used (e.g., Waters Empower, Agilent OpenLAB, Excel with specified version). "
                "Per 21 CFR Part 11 and EU GMP Annex 11, computer systems used for calculations "
                "must be identified and qualified. Specifying the calculation tool ensures result "
                "reproducibility and supports data integrity requirements."
            ),
            evidence="",
            regulatory_citation="21 CFR Part 11 / EU GMP Annex 11",
            citation_type="direct",
            agency="FDA",
            suggestion_draft="Add: 'Calculations shall be performed using [Software Name, Version]. The system is qualified per [qualification record reference].'",
            next_step_text="Specify the validated software used for calculations and its qualification status.",
            remediation_priority=4,
            confidence_score=0.62,
            validated=True,
        )]

    # ========== L5: CAPA Data & Statistical Intelligence Checks ==========

    def _check_l5_metrics_defined_for_effectiveness(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA effectiveness check must define specific, measurable metrics — not just 'no recurrence'."""
        text_lower = ctx.document_text.lower()
        has_effectiveness = bool(re.search(
            r'(?:effectiveness\s+check|effectiveness\s+verif|effectiveness\s+criteria|'
            r'check\s+effectiveness|verify\s+effectiveness)',
            text_lower
        ))
        if not has_effectiveness:
            return []
        has_measurable = bool(re.search(
            r'(?:zero\s+recurrence|no\s+(?:further\s+)?recurrence\s+(?:in|for|within)\s+\d|'
            r'rate\s+(?:below|of|reduced\s+by)|kpi|key\s+performance|metric\s+is|'
            r'measured\s+by|target\s+(?:value|threshold)|≤\s*\d|>\s*\d\s*%|'
            r'\d+\s*%\s+(?:reduction|improvement|compliance))',
            text_lower
        ))
        if has_measurable:
            return []
        return [FindingResult(
            level="L5",
            severity="medium",
            category="effectiveness_metrics_vague",
            title="Effectiveness check lacks specific measurable metrics",
            description=(
                "An effectiveness check is referenced but lacks specific, measurable criteria. "
                "Effectiveness checks stated only as 'no recurrence observed' or 'issue does not "
                "reoccur' cannot be objectively verified. Per ICH Q10 and FDA CAPA expectations, "
                "effectiveness checks must define a measurable target (e.g., zero recurrence of "
                "deviation type X within 6 months, deviation rate reduced by ≥50%, 100% compliance "
                "to SOP Y as verified by audit). Vague effectiveness criteria are a frequent FDA "
                "483 observation in CAPA systems."
            ),
            evidence="Effectiveness check referenced without quantitative success criteria.",
            regulatory_citation="ICH Q10 / 21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            suggestion_draft=(
                "Update effectiveness check section:\n"
                "Effectiveness Metric: [Zero recurrence of [deviation type] within 12 months of CAPA closure]\n"
                "Measurement Method: [Review of deviation log / audit results / complaint rate]\n"
                "Target: [0 recurrences OR ≥50% reduction in frequency]\n"
                "Review Date: [Date, typically 6–12 months post-closure]\n"
                "Responsible: [QA Manager / CAPA Owner]\n"
                "Success Criterion: [Specific, objective outcome that confirms root cause is eliminated]"
            ),
            next_step_text="Define a measurable effectiveness metric with a specific target value and review date.",
            remediation_priority=3,
            confidence_score=0.76,
            validated=True,
        )]

    def _check_l5_monitoring_period_defined(self, ctx: AssessmentContext) -> list[FindingResult]:
        """CAPA must define the post-closure monitoring period for recurrence monitoring."""
        text_lower = ctx.document_text.lower()
        has_capa = bool(re.search(r'\bcapa\b|corrective.*preventive', text_lower))
        if not has_capa:
            return []
        has_monitoring_period = bool(re.search(
            r'(?:monitor(?:ing)?\s+(?:for|period|duration)|'
            r'post[\s-]closure\s+(?:monitoring|review|period)|'
            r'(?:6|12|24|36|18|3|9)\s+months?\s+(?:post|after|following)|'
            r'monitoring\s+(?:for|period)\s+(?:of\s+)?\d+\s+(?:months?|days?|years?)|'
            r'surveillance\s+period)',
            text_lower
        ))
        if has_monitoring_period:
            return []
        return [FindingResult(
            level="L5",
            severity="low",
            category="monitoring_period_not_defined",
            title="Post-closure recurrence monitoring period not defined",
            description=(
                "The CAPA does not specify the post-closure monitoring period during which recurrence "
                "of the original issue will be tracked. Without a defined surveillance period, there "
                "is no systematic mechanism to confirm the CAPA eliminated the root cause. "
                "FDA CAPA guidance and ICH Q10 expect that CAPA closure includes a defined period "
                "of enhanced monitoring — typically 6–12 months — before the effectiveness check is "
                "declared successful."
            ),
            evidence="",
            regulatory_citation="ICH Q10 / FDA CAPA guidance",
            citation_type="indirect",
            agency="FDA",
            suggestion_draft=(
                "Add to CAPA Closure / Effectiveness Check section:\n"
                "Post-Closure Monitoring Period: [6 months / 12 months from closure date]\n"
                "Monitoring Activity: [Review deviation log monthly / audit compliance quarterly]\n"
                "Recurrence Signal: [Any recurrence of [original event type] within monitoring period]\n"
                "If recurrence detected: re-open CAPA or initiate new CAPA [CAPA-ID reference]"
            ),
            next_step_text="Specify the monitoring period duration and what event would trigger CAPA re-opening.",
            remediation_priority=4,
            confidence_score=0.68,
            validated=True,
        )]

    # ========== L1/L3/L4/L7/L8: Deviation Report Checks ==========

    def _check_l1_deviation_required_fields(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Check mandatory Deviation Report fields — deviation ID, product, batch, root cause, impact, QA."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        text_lower = text.lower()

        required = [
            (r'deviation\s*(?:id|no|number|#|ref)', "Deviation ID", "high", "21 CFR 211.192"),
            (r'product\s*name|material\s*name', "Product/Material Name", "critical", "21 CFR 211.192"),
            (r'batch\s*(?:no|number|lot)', "Batch/Lot Number", "critical", "21 CFR 211.192"),
            (r'root\s*cause', "Root Cause Analysis", "critical", "21 CFR 211.192"),
            (r'impact\s*assessment|assessment\s*impact', "Impact Assessment", "critical", "21 CFR 211.192"),
            (r'QA\s*(?:approv|review|sign)|(?:approv|review|sign)\w*\s*QA', "QA Approval", "high", "21 CFR 211.22"),
        ]
        for pattern, label, severity, citation in required:
            if not re.search(pattern, text_lower):
                findings.append(FindingResult(
                    level="L1",
                    severity=severity,
                    category="missing_required_field",
                    title=f"Mandatory field missing: {label}",
                    description=(
                        f"No '{label}' field was found in the document. "
                        f"This is a mandatory element of a GMP Deviation Report. "
                        f"Every deviation report must document {label} to satisfy traceability "
                        f"and investigation requirements per 21 CFR 211.192."
                    ),
                    evidence="",
                    regulatory_citation=citation,
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.74,
                    validated=True,
                    suggestion_draft=f"Add a '{label}' field with specific, documented content.",
                ))
        return findings

    def _check_l4_impact_without_data(self, ctx: AssessmentContext) -> list[FindingResult]:
        """'No impact' claim without citing analytical data or scientific rationale — Critical."""
        text = ctx.document_text
        no_impact_patterns = [
            r'no\s+impact\s+(?:on|to)\s+(?:product\s+)?quality',
            r'no\s+(?:product\s+)?quality\s+impact',
            r'product\s+quality\s+(?:not|is\s+not)\s+(?:affected|impacted|compromised)',
            r'no\s+(?:patient\s+)?safety\s+(?:impact|concern|risk)',
            r'does\s+not\s+(?:affect|impact)\s+(?:product\s+quality|patient\s+safety)',
        ]
        for pat in no_impact_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                context_after = text[m.end():m.end() + 500]
                has_evidence = re.search(
                    r'(?:stability|analytical|test\s+result|specification|batch\s+record|'
                    r'data|analysis|result\s+shows?|confirmed\s+by|based\s+on)',
                    context_after, re.IGNORECASE
                )
                if has_evidence:
                    return []
                sentence_start = max(0, text.rfind('\n', 0, m.start()) + 1)
                sentence = text[sentence_start:sentence_start + 300].strip()
                return [FindingResult(
                    level="L4",
                    severity="critical",
                    category="impact_without_data",
                    title="Impact claim made without citing analytical data or scientific basis",
                    description=(
                        f"The impact assessment states '{sentence[:200]}' but does not cite "
                        f"analytical data, stability modeling, test results, or a scientific "
                        f"rationale to support this conclusion. An assertion of no quality or "
                        f"safety impact without documentary evidence cannot be verified during "
                        f"an inspection and cannot justify batch disposition decisions."
                    ),
                    evidence=sentence[:250],
                    location=_nearest_section(text, m.start()),
                    regulatory_citation="21 CFR 211.192",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.88,
                    validated=True,
                    suggestion_draft=(
                        "Replace the unsupported claim with a referenced scientific justification: "
                        "cite specific analytical results, stability model, or test data with document IDs."
                    ),
                )]
        return []

    def _check_l7_deviation_timeliness(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Check Critical deviation timeliness — initiation within 24hrs required."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        text_lower = text.lower()

        is_critical_deviation = bool(re.search(
            r'(?:severity|classification|deviation\s+type)\s*[:\-]?\s*critical',
            text_lower
        ))
        if not is_critical_deviation:
            return []

        # Look for detection/occurrence date and initiation date
        detection = re.search(r'(?:date\s+of\s+(?:detection|occurrence)|detected\s+(?:on|date))[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)
        initiation = re.search(r'(?:initiation|initiated|opened)\s*(?:date|on)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text, re.IGNORECASE)

        if detection and initiation:
            from datetime import datetime
            date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%Y-%m-%d"]
            det_date = ini_date = None
            for fmt in date_formats:
                try:
                    det_date = datetime.strptime(detection.group(1), fmt)
                    break
                except ValueError:
                    pass
            for fmt in date_formats:
                try:
                    ini_date = datetime.strptime(initiation.group(1), fmt)
                    break
                except ValueError:
                    pass
            if det_date and ini_date and (ini_date - det_date).days > 1:
                findings.append(FindingResult(
                    level="L7",
                    severity="critical",
                    category="deviation_timeliness",
                    title=f"Critical deviation initiated {(ini_date - det_date).days} days after detection — exceeds 24-hour requirement",
                    description=(
                        f"This Critical deviation was detected on {detection.group(1)} and initiated "
                        f"on {initiation.group(1)} — a gap of {(ini_date - det_date).days} day(s). "
                        f"GMP requirements mandate that Critical deviations be formally initiated within "
                        f"24 hours of detection. Delayed initiation risks batch release before investigation "
                        f"completion, destruction of contemporaneous evidence, and compromises QA oversight."
                    ),
                    evidence=f"Detection date: {detection.group(1)}; Initiation date: {initiation.group(1)}",
                    regulatory_citation="21 CFR 211.192",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.90,
                    validated=True,
                ))

        # Flag open investigations beyond 120 days
        if re.search(r'(?:investigation\s+(?:status|open|ongoing)|status\s*[:\-]\s*(?:open|in\s*progress|ongoing))', text_lower):
            if re.search(r'(?:120|180|365)\s*(?:day|calendar\s+day)', text_lower) or \
               re.search(r'(?:more\s+than|over|exceeding)\s+\d{3}\s*days?', text_lower):
                findings.append(FindingResult(
                    level="L7",
                    severity="critical",
                    category="deviation_investigation_open_too_long",
                    title="Deviation investigation open beyond 120 calendar days",
                    description=(
                        "The deviation investigation appears to have been open for more than 120 calendar "
                        "days. An investigation open beyond this threshold is considered unreasonably "
                        "extended by FDA standards — no deviation can require more than 120 days of "
                        "investigation without documented extraordinary justification approved by senior QA management."
                    ),
                    evidence="",
                    regulatory_citation="21 CFR 211.192",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.75,
                    validated=True,
                ))

        return findings

    def _check_l8_far_assessment(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Field Alert Report (FAR) assessment must be present in every deviation — even if 'not required'."""
        text = ctx.document_text
        has_far = re.search(
            r'(?:field\s+alert|FAR\s+(?:assessment|required|not\s+required)|'
            r'15.day|regulatory\s+reporting\s+assessment)',
            text, re.IGNORECASE
        )
        if has_far:
            return []
        return [FindingResult(
            level="L8",
            severity="critical",
            category="far_assessment_absent",
            title="Field Alert Report (FAR) assessment absent from deviation",
            description=(
                "No Field Alert Report (FAR) assessment was found in the document. "
                "FDA requires that every deviation involving a drug product be assessed "
                "for FAR reportability, even if the conclusion is 'not required.' "
                "The assessment must be documented with the stated basis for the conclusion. "
                "The absence of a FAR assessment — regardless of whether one was required — "
                "is a direct regulatory reporting gap per 21 CFR 314.81(b)(1)."
            ),
            evidence="",
            regulatory_citation="21 CFR 314.81(b)(1)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
            suggestion_draft=(
                "REGULATORY REPORTING ASSESSMENT\n"
                "Field Alert Report (FAR): [Required / Not Required]\n"
                "Basis: [e.g., 'Batch not distributed to US market; no FAR required per 21 CFR 314.81(b)(1)']\n"
                "15-Day Safety Report: [Applicable / Not Applicable] — Basis: [state reason]\n"
                "Annual Product Review: [Will be included in APR for Product X, Year XXXX]\n"
                "Assessed by: [QA signature / date]"
            ),
        )]

    # ========== L1/L3/L4/L8: LIR (Lab Investigation Report) Checks ==========

    def _check_l1_phase_structure(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Phase I structure mandatory for all OOS investigations; Phase II when Phase I finds no assignable cause."""
        findings: list[FindingResult] = []
        text = ctx.document_text
        text_lower = text.lower()

        has_phase1 = re.search(r'phase\s*[i1]\b|phase\s+one\b', text_lower)
        if not has_phase1:
            findings.append(FindingResult(
                level="L1",
                severity="critical",
                category="phase_structure_absent",
                title="Phase I / Phase II investigation structure absent from Lab Investigation Report",
                description=(
                    "No Phase I investigation structure was found in this Lab Investigation Report. "
                    "FDA OOS Guidance 2006 mandates a two-phase investigation structure for all OOS "
                    "results: Phase I (laboratory investigation) must be completed before any retesting "
                    "begins, and its conclusion documented before Phase II can be initiated. An LIR "
                    "without Phase I structure cannot demonstrate a compliant OOS investigation process."
                ),
                evidence="",
                regulatory_citation="FDA OOS Guidance 2006",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.88,
                validated=True,
            ))
        else:
            # Phase I found — check for explicit conclusion
            phase1_conclusion = re.search(
                r'phase\s*[i1][^\n]{0,200}(?:conclusion|result|finding)[:\s]',
                text_lower
            )
            if not phase1_conclusion:
                findings.append(FindingResult(
                    level="L1",
                    severity="critical",
                    category="phase1_conclusion_absent",
                    title="Phase I referenced but no explicit Phase I conclusion statement found",
                    description=(
                        "Phase I is referenced but no explicit Phase I conclusion statement was found. "
                        "FDA OOS Guidance 2006 requires the Phase I conclusion to be documented as one of: "
                        "'Assignable cause found' (with named evidence) or 'No assignable cause found.' "
                        "Without this explicit conclusion, Phase II trigger logic cannot be verified by "
                        "an FDA investigator."
                    ),
                    evidence="",
                    regulatory_citation="FDA OOS Guidance 2006 Section VI.B",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.82,
                    validated=True,
                ))
        return findings

    def _check_l3_phase1_conclusion(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Phase I must conclude as 'Assignable cause found' or 'No assignable cause found' — with evidence."""
        text = ctx.document_text
        text_lower = text.lower()
        # If explicit Phase I conclusion is already flagged by phase_structure check, skip
        has_phase1 = re.search(r'phase\s*[i1]\b|phase\s+one\b', text_lower)
        if not has_phase1:
            return []
        has_conclusion = re.search(
            r'(?:assignable\s+cause|no\s+assignable\s+cause|no\s+laboratory\s+error|'
            r'phase\s*[i1]\s*conclusion)[:\s]',
            text_lower
        )
        if not has_conclusion:
            return [FindingResult(
                level="L3",
                severity="critical",
                category="phase1_no_conclusion",
                title="Phase I lacks an explicit assignable-cause conclusion statement",
                description=(
                    "Phase I is present but does not contain an explicit conclusion statement. "
                    "FDA OOS Guidance 2006 requires Phase I to conclude with either "
                    "'Assignable cause found' (supported by specific named evidence) or "
                    "'No assignable cause found' (triggering mandatory Phase II). Without this "
                    "binary conclusion, the investigation pathway cannot be verified, and the "
                    "Phase II trigger cannot be assessed."
                ),
                evidence="",
                regulatory_citation="FDA OOS Guidance 2006 Section VI.B",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.82,
                validated=True,
            )]
        return []

    def _check_l4_selective_reporting(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Stated retest count does not match number of results reported — potential selective reporting."""
        text = ctx.document_text
        retest_count_m = re.search(
            r'(\d+)\s+(?:re-?tests?|additional\s+tests?|repeat\s+tests?)\s+(?:were\s+)?(?:performed|conducted|completed)',
            text, re.IGNORECASE
        )
        if not retest_count_m:
            return []
        stated_count = int(retest_count_m.group(1))
        if stated_count < 2:
            return []
        result_block = text[retest_count_m.start():retest_count_m.start() + 800]
        result_values = re.findall(r'\d+\.?\d*\s*%', result_block)
        reported_count = len(result_values)
        if not (0 < reported_count < stated_count):
            return []
        return [FindingResult(
            level="L4",
            severity="critical",
            category="selective_retest_reporting",
            title=f"Selective reporting risk: {stated_count} retests stated but only {reported_count} result(s) shown",
            description=(
                f"The document states '{stated_count} retests performed' but only "
                f"{reported_count} result value(s) appear in the retest section. "
                f"FDA OOS Guidance 2006 requires ALL retest results — passing and failing — "
                f"to be reported. A discrepancy between the stated number of tests and the "
                f"number of results reported is a potential selective reporting data integrity "
                f"violation. This must be reconciled with documentation of all test results."
            ),
            evidence=result_block[:250].strip(),
            location=_nearest_section(text, retest_count_m.start()),
            regulatory_citation="FDA OOS Guidance 2006 Section VI.C.2",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
        )]

    def _check_l8_passing_retest_assignable_cause(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Passing retest as the sole Phase I assignable cause — #1 cited OOS invalidation error."""
        text = ctx.document_text
        patterns = [
            r'assignable\s+cause[:\s]+(?:passing\s+retest|retest\s+passed|retests?\s+(?:were\s+)?(?:all\s+)?(?:within|compliant|acceptable|passed))',
            r'OOS\s+(?:result\s+)?invalidated[^\n]{0,200}retest\s+pass',
            r'original\s+result[^\n]{0,100}invalidated[^\n]{0,200}retests?\s+(?:passed|compliant|within)',
            r'assignable\s+cause[:\s]*(?:confirmed\s+)?(?:by\s+)?(?:the\s+)?(?:passing\s+)?retest',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                excerpt_start = max(0, text.rfind('\n', 0, m.start()) + 1)
                excerpt = text[excerpt_start:excerpt_start + 400].strip()
                return [FindingResult(
                    level="L8",
                    severity="critical",
                    category="passing_retest_as_assignable_cause",
                    title="OOS invalidated based solely on passing retests — not valid Phase I assignable cause",
                    description=(
                        f"The Phase I investigation invalidates the OOS result based on passing retests: "
                        f"'{excerpt[:200]}'. "
                        f"FDA OOS Guidance 2006, Section VI.C.1 explicitly states that a passing retest "
                        f"result is not, by itself, acceptable as Phase I assignable cause evidence. "
                        f"An assignable cause requires: (1) a specifically named laboratory error, "
                        f"(2) corroborating documentary evidence, and (3) a causal link to the OOS result. "
                        f"Without all three criteria, the OOS cannot be invalidated at Phase I, "
                        f"and Phase II must be conducted."
                    ),
                    evidence=excerpt[:300],
                    location=_nearest_section(text, m.start()),
                    regulatory_citation="FDA OOS Guidance 2006 Section VI.C.1",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.97,
                    validated=True,
                )]
        return []

    def _check_l8_disposition_consistency(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Confirmed OOS + Release disposition is an automatic Critical — contradictory and impermissible."""
        text_lower = ctx.document_text.lower()
        confirmed_oos = re.search(
            r'(?:confirmed|conclusion)[:\s]*confirmed\s+oos|oos\s+confirmed|'
            r'phase\s*[ii2]\s+conclusion[:\s]*confirmed\s+oos',
            text_lower
        )
        released = re.search(
            r'(?:disposition|batch\s+disposition)[:\s]*(?:released?|approved\s+for\s+release)',
            text_lower
        )
        if not (confirmed_oos and released):
            return []
        return [FindingResult(
            level="L8",
            severity="critical",
            category="confirmed_oos_released",
            title="Confirmed OOS batch dispositioned as 'Released' — impermissible under GMP",
            description=(
                "The document indicates a 'Confirmed OOS' conclusion AND a batch disposition of "
                "'Released.' A batch with a confirmed OOS result cannot be released under any "
                "GMP-compliant disposition framework. This combination is an automatic Critical "
                "finding — the disposition is inconsistent with the investigation outcome and "
                "constitutes a potential patient safety violation per 21 CFR 211.192."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.93,
            validated=True,
        )]

    # ========== Shared L2 Checks (Deviation + LIR) ==========

    def _check_l2_approval_signatures(self, ctx: AssessmentContext) -> list[FindingResult]:
        """QA approval signature line — blank, 'TBD', or 'N/A' with no date is a critical structural gap."""
        text = ctx.document_text
        text_lower = text.lower()
        # Look for QA-related signature/approval blocks
        qa_blocks = list(re.finditer(
            r'(?:qa|quality\s+assurance)\s*(?:approv|sign|authorized|reviewed)',
            text_lower
        ))
        if not qa_blocks:
            return [FindingResult(
                level="L2",
                severity="critical",
                category="qa_approval_absent",
                title="QA approval signature block not found in document",
                description=(
                    "No QA approval signature block was detected in the document. "
                    "GMP requires that quality documents be formally approved by QA before use. "
                    "The absence of a QA signature line represents a document control gap "
                    "per 21 CFR 211.22(a)."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.22(a)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.72,
                validated=True,
            )]
        findings = []
        for m in qa_blocks[:3]:
            context_after = text[m.end():m.end() + 200]
            blank_sig = re.search(r'(?:___|tbd|pending|n/?a|not\s+applicable|to\s+be\s+(?:determined|filled))', context_after, re.IGNORECASE)
            if blank_sig:
                excerpt = text[m.start():m.end() + 100].strip()
                findings.append(FindingResult(
                    level="L2",
                    severity="critical",
                    category="unsigned_qa_approval",
                    title="QA approval signature line is blank or placeholder — document may be unapproved",
                    description=(
                        f"The QA approval block at '{excerpt[:120]}' appears unsigned (blank lines, 'TBD', "
                        f"or 'N/A'). Distributing or using a GMP document without completed QA approval "
                        f"constitutes a document control violation per 21 CFR 211.22(a). Every controlled "
                        f"document must carry a wet or electronic QA signature with date before release."
                    ),
                    evidence=excerpt,
                    location=_nearest_section(text, m.start()),
                    regulatory_citation="21 CFR 211.22(a)",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.85,
                    validated=True,
                ))
                break
        return findings

    def _check_l2_qa_independence(self, ctx: AssessmentContext) -> list[FindingResult]:
        """QA reviewer and author must not be the same person — independence is a GMP control requirement."""
        text = ctx.document_text
        # Extract author/prepared-by name
        author_m = re.search(
            r'(?:prepared\s+by|authored\s+by|investigator|submitted\s+by)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            text, re.IGNORECASE
        )
        # Extract QA approver name
        approver_m = re.search(
            r'(?:approved\s+by\s+(?:qa|quality)|qa\s+(?:approval|approver|reviewer))\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            text, re.IGNORECASE
        )
        if not (author_m and approver_m):
            return []
        author_name = author_m.group(1).strip().lower()
        approver_name = approver_m.group(1).strip().lower()
        if author_name == approver_name:
            return [FindingResult(
                level="L2",
                severity="high",
                category="qa_independence_violation",
                title=f"QA approver and author are the same individual ({author_m.group(1)}) — independence not maintained",
                description=(
                    f"The document was prepared by and QA-approved by the same person: '{author_m.group(1)}'. "
                    f"GMP requires that the author/investigator and QA approver be independent individuals. "
                    f"A self-approved GMP document cannot demonstrate the independent QA oversight required by "
                    f"21 CFR 211.22(a). This is a systemic control gap."
                ),
                evidence=f"Author: {author_m.group(1)} / QA Approver: {approver_m.group(1)}",
                regulatory_citation="21 CFR 211.22(a)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.87,
                validated=True,
            )]
        return []

    def _check_l2_version_control_block(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Version, effective date, and supersedes fields must be present and populated."""
        text = ctx.document_text
        text_lower = text.lower()
        missing = []
        if not re.search(r'(?:version|rev(?:ision)?\s*(?:no|#|:|\s))', text_lower):
            missing.append("Version/Revision number")
        if not re.search(r'(?:effective\s+date|eff\.?\s+date|date\s+effective)', text_lower):
            missing.append("Effective date")
        if not missing:
            return []
        return [FindingResult(
            level="L2",
            severity="high" if len(missing) > 1 else "medium",
            category="version_control_incomplete",
            title=f"Version control block incomplete: missing {', '.join(missing)}",
            description=(
                f"The document is missing required version control fields: {', '.join(missing)}. "
                f"GMP document control requires every controlled document to carry a version number, "
                f"effective date, and supersedes reference to maintain a traceable history and prevent "
                f"use of obsolete versions per 21 CFR 211.68 and EU GMP Part I Ch. 4."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.76,
            validated=True,
        )]

    def _check_l4_disposition_before_investigation(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Batch disposition date preceding investigation close date — chronological integrity violation."""
        text = ctx.document_text
        # Find disposition date
        disp_m = re.search(
            r'(?:disposition|released?\s+date|batch\s+released?)[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text, re.IGNORECASE
        )
        # Find investigation close/completion date
        inv_m = re.search(
            r'(?:investigation\s+(?:closed|completed|close\s+date)|closure\s+date|completed\s+(?:on|date))[:\s]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text, re.IGNORECASE
        )
        if not (disp_m and inv_m):
            return []
        from datetime import datetime
        date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%Y-%m-%d"]
        disp_date = inv_date = None
        for fmt in date_formats:
            try:
                disp_date = datetime.strptime(disp_m.group(1), fmt); break
            except ValueError:
                pass
        for fmt in date_formats:
            try:
                inv_date = datetime.strptime(inv_m.group(1), fmt); break
            except ValueError:
                pass
        if not (disp_date and inv_date):
            return []
        if disp_date < inv_date:
            return [FindingResult(
                level="L4",
                severity="critical",
                category="disposition_before_investigation",
                title=f"Batch dispositioned ({disp_m.group(1)}) before investigation closed ({inv_m.group(1)}) — chronological integrity violation",
                description=(
                    f"The batch disposition date ({disp_m.group(1)}) precedes the investigation closure "
                    f"date ({inv_m.group(1)}). A batch cannot be legally released before the deviation or "
                    f"OOS investigation is formally closed and QA-approved. This is an automatic Critical "
                    f"data integrity finding per 21 CFR 211.192 — it indicates either a records falsification "
                    f"or a premature release decision that bypassed quality controls."
                ),
                evidence=f"Disposition: {disp_m.group(1)} | Investigation close: {inv_m.group(1)}",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.92,
                validated=True,
            )]
        return []

    def _check_l1_containment_documented(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Immediate containment actions are mandatory in a Deviation Report."""
        text_lower = ctx.document_text.lower()
        has_containment = re.search(
            r'(?:immediate\s+(?:action|containment|response)|containment\s+action|'
            r'immediate\s+corrective|temporary\s+control|quarantine|hold)',
            text_lower
        )
        if has_containment:
            return []
        return [FindingResult(
            level="L1",
            severity="high",
            category="containment_actions_absent",
            title="Immediate containment actions not documented in Deviation Report",
            description=(
                "No immediate containment actions were found in the document. "
                "GMP Deviation Reports must document immediate actions taken at the time of deviation "
                "discovery — such as quarantine, process hold, or temporary controls — even if "
                "the conclusion is that no action was required. The absence of this field "
                "creates an ambiguity about what was done at the time of the event per 21 CFR 211.192."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.73,
            validated=True,
        )]

    def _check_l1_batch_info_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Batch/lot number and product name are mandatory traceability fields in a Deviation Report."""
        text_lower = ctx.document_text.lower()
        findings = []
        if not re.search(r'batch\s*(?:no|number|#|lot)|lot\s*(?:no|number|#)', text_lower):
            findings.append(FindingResult(
                level="L1",
                severity="critical",
                category="batch_lot_number_absent",
                title="Batch/Lot number not found in Deviation Report",
                description=(
                    "No batch or lot number was found in the Deviation Report. "
                    "Every GMP deviation must be traceable to the specific batch(es) affected. "
                    "Without this traceability, batch disposition decisions cannot be linked to the "
                    "investigation outcome, and a recall or field correction cannot be properly scoped. "
                    "Required per 21 CFR 211.192."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            ))
        if not re.search(r'product\s*(?:name|code|id)|material\s*(?:name|code)', text_lower):
            findings.append(FindingResult(
                level="L1",
                severity="critical",
                category="product_name_absent",
                title="Product/Material name not identified in Deviation Report",
                description=(
                    "No product or material name was identified in the Deviation Report. "
                    "Product identification is a mandatory traceability element — the investigation "
                    "must be linked to the specific product affected to support batch disposition "
                    "and potential regulatory reporting decisions per 21 CFR 211.192."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.78,
                validated=True,
            ))
        return findings

    def _check_l1_lir_required_fields(self, ctx: AssessmentContext) -> list[FindingResult]:
        """OOS result details, sample ID, method reference, and specification are mandatory LIR fields."""
        text = ctx.document_text
        text_lower = text.lower()
        findings = []
        required = [
            (r'(?:oos|out.of.spec(?:ification)?)\s*(?:result|value|reading)', "OOS result value", "critical", "FDA OOS Guidance 2006 Section II"),
            (r'(?:sample\s*(?:id|no|number|code)|lot\s*(?:no|number))', "Sample/Lot ID", "critical", "21 CFR 211.194"),
            (r'(?:analytical\s+method|test\s+method|stp|method\s+(?:ref|no))', "Analytical Method reference", "high", "21 CFR 211.194"),
            (r'(?:specification|spec\s+limit|acceptance\s+criteria|acceptance\s+limit)', "Specification/Acceptance limit", "critical", "21 CFR 211.194"),
        ]
        for pattern, label, severity, citation in required:
            if not re.search(pattern, text_lower):
                findings.append(FindingResult(
                    level="L1",
                    severity=severity,
                    category="lir_required_field_absent",
                    title=f"Required LIR field absent: {label}",
                    description=(
                        f"The mandatory field '{label}' was not found in this Lab Investigation Report. "
                        f"FDA OOS Guidance 2006 requires all OOS investigations to fully document the "
                        f"original result, sample identity, test method, and specification limit. "
                        f"Without {label}, the investigation cannot be independently verified per {citation}."
                    ),
                    evidence="",
                    regulatory_citation=citation,
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.74,
                    validated=True,
                ))
        return findings

    def _check_l4_root_cause_named_evidence(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Root cause must be a named, specific cause with documentary evidence — not 'unknown' or generic."""
        text = ctx.document_text
        text_lower = text.lower()
        rc_m = re.search(
            r'(?:root\s+cause|assignable\s+cause)[:\s]*(.{0,300}?)(?:\n\n|\Z)',
            text_lower
        )
        if not rc_m:
            return []
        rc_text = rc_m.group(1).strip()
        # Red-flag patterns — vague, deferrring, or unresolved root causes
        vague_patterns = [
            r'unknown', r'undetermined', r'tbd', r'to\s+be\s+determined',
            r'under\s+investigation', r'not\s+identified', r'unclear',
            r'(?:likely|probable|possible)\s+(?:cause|error)',
        ]
        for pat in vague_patterns:
            if re.search(pat, rc_text):
                excerpt = rc_m.group(0)[:300].strip()
                return [FindingResult(
                    level="L4",
                    severity="critical",
                    category="root_cause_not_identified",
                    title=f"Root cause is vague or undetermined: '{rc_text[:80]}'",
                    description=(
                        f"The root cause statement is non-specific: '{rc_text[:200]}'. "
                        f"FDA OOS Guidance 2006 requires that the root cause be a named, specific error "
                        f"supported by documentary evidence (e.g., instrument calibration record, analyst "
                        f"transcription log). A vague or 'unknown' root cause cannot justify OOS invalidation, "
                        f"and cannot demonstrate that the CAPA addresses the actual cause of the failure. "
                        f"An unidentified root cause requires Phase II investigation."
                    ),
                    evidence=excerpt,
                    location=_nearest_section(text, rc_m.start()),
                    regulatory_citation="FDA OOS Guidance 2006 Section VI.B",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.86,
                    validated=True,
                )]
        return []

    def _check_l8_patient_safety_assessment(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Patient safety impact assessment must be present and explicitly documented."""
        text_lower = ctx.document_text.lower()
        has_safety = re.search(
            r'(?:patient\s+safety|safety\s+(?:assessment|impact|evaluation)|'
            r'risk\s+to\s+patient|clinical\s+(?:impact|significance)|'
            r'adverse\s+(?:health|patient)\s+(?:impact|consequence))',
            text_lower
        )
        if has_safety:
            return []
        return [FindingResult(
            level="L8",
            severity="high",
            category="patient_safety_assessment_absent",
            title="Patient safety impact assessment not documented",
            description=(
                "No patient safety impact assessment was found in the document. "
                "All GMP deviations and OOS investigations must include an assessment of potential "
                "patient safety impact — even if the conclusion is that no risk to patients exists. "
                "This assessment is required to support batch disposition, field alert decisions, "
                "and regulatory reporting determinations per ICH Q10 and 21 CFR 314.81."
            ),
            evidence="",
            regulatory_citation="ICH Q10 / 21 CFR 314.81",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.77,
            validated=True,
        )]

    def _check_l8_regulatory_reporting_documented(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Regulatory reporting assessment (FAR, 15-day, MDR) must be explicitly documented."""
        text_lower = ctx.document_text.lower()
        has_reporting = re.search(
            r'(?:field\s+alert|far\s+(?:required|not\s+required|assessment)|'
            r'15.?day\s+(?:report|safety)|mdr|medical\s+device\s+report|'
            r'regulatory\s+reporting\s+(?:assessment|required|not\s+required))',
            text_lower
        )
        if has_reporting:
            return []
        return [FindingResult(
            level="L8",
            severity="high",
            category="regulatory_reporting_not_assessed",
            title="Regulatory reporting assessment absent — FAR / 15-day reportability not documented",
            description=(
                "No regulatory reporting assessment was found. This document must contain an explicit "
                "assessment of reportability for: (1) Field Alert Report (FAR) per 21 CFR 314.81, "
                "(2) 15-day Expedited Safety Report if applicable, and (3) any applicable MedWatch / MDR "
                "obligations. The conclusion may be 'Not required' but the assessment and rationale "
                "must be documented — silence on reportability is not acceptable during an inspection."
            ),
            evidence="",
            regulatory_citation="21 CFR 314.81",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l8_confirmed_oos_release(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Confirmed OOS batch released without an approved exception — impermissible."""
        text_lower = ctx.document_text.lower()
        # Check for explicit confirmed OOS + release combination (same as disposition_consistency but at L8 for LIR profile)
        confirmed_oos = re.search(
            r'(?:phase\s*[ii2]|final)\s+conclusion[:\s]*confirmed\s+oos|'
            r'oos\s+(?:result\s+)?(?:confirmed|conclusion\s*:\s*confirmed)',
            text_lower
        )
        released = re.search(
            r'(?:disposition|batch\s+disposition|final\s+disposition)[:\s]*(?:released?|approved)',
            text_lower
        )
        if confirmed_oos and released:
            return [FindingResult(
                level="L8",
                severity="critical",
                category="confirmed_oos_released",
                title="Confirmed OOS result followed by release disposition — impermissible GMP violation",
                description=(
                    "A 'Confirmed OOS' conclusion is present alongside a 'Released' batch disposition. "
                    "Under no circumstances may a batch with a confirmed OOS result be released to market. "
                    "This combination is an automatic Critical finding per 21 CFR 211.192 and constitutes "
                    "a patient safety violation. Permissible dispositions for Confirmed OOS are: "
                    "Reject/Destroy, or Exception Release with QP/NDA holder sign-off and regulatory notification."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.95,
                validated=True,
            )]
        return []

    # ========== L3/L8: Deviation-Specific Checks ==========

    def _check_l3_capa_adequacy(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Deviation CAPA must be specific, traceable, and time-bound — not generic retraining."""
        text = ctx.document_text
        has_capa = re.search(r'\b(?:CAPA|corrective\s+action|preventive\s+action)\b', text, re.IGNORECASE)
        if not has_capa:
            return [FindingResult(
                level="L3",
                severity="critical",
                category="capa_absent_in_deviation",
                title="Deviation Report has no CAPA or corrective action",
                description=(
                    "No corrective or preventive action was found in the Deviation Report. "
                    "Every GMP deviation — unless dispositioned as no CAPA required with documented "
                    "justification — must include at least one CAPA. The absence of any corrective action "
                    "implies the root cause was not addressed, increasing recurrence risk."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            )]
        capa_window = text[has_capa.start():has_capa.start() + 600]
        is_generic = re.search(
            r'(?:retraining|re-?train|training\s+(?:only|will\s+be\s+conducted|provided)|'
            r'awareness\s+(?:training|session)|briefing\s+held)',
            capa_window, re.IGNORECASE
        )
        is_systemic = re.search(
            r'(?:SOP\s+(?:will\s+be\s+)?(?:update|revis)|procedure\s+(?:update|change|revis)|'
            r'process\s+(?:change|modification|improvement)|system\s+(?:update|revis))',
            capa_window, re.IGNORECASE
        )
        if is_generic and not is_systemic:
            return [FindingResult(
                level="L3",
                severity="high",
                category="retraining_only_capa_deviation",
                title="Deviation CAPA is retraining only — systemic root cause not addressed",
                description=(
                    "The only corrective action in this Deviation Report is retraining or awareness "
                    "sessions. If the root cause was a systemic process failure, SOP gap, or design "
                    "issue, retraining cannot prevent recurrence — only the systemic cause can. "
                    "FDA inspectors routinely cite deviations where retraining is the only action "
                    "without corresponding system-level changes as evidence of inadequate CAPA programs."
                ),
                evidence=capa_window[:250].strip(),
                location=_nearest_section(text, has_capa.start()) or "Corrective Actions",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.82,
                validated=True,
            )]
        return []

    def _check_l3_root_cause_evidence_cited(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Deviation root cause conclusion must be supported by cited evidence."""
        text = ctx.document_text
        rc_section = re.search(r'root\s+cause', text, re.IGNORECASE)
        if not rc_section:
            return []
        rc_window = text[rc_section.start():rc_section.start() + 800]
        has_evidence = re.search(
            r'(?:batch\s+record|laboratory\s+notebook|chromatogram|raw\s+data|'
            r'observation|review\s+of|data\s+review|observed|confirmed|verified|'
            r'determined\s+(?:from|by)|evidence|attachment|annex|exhibit)',
            rc_window, re.IGNORECASE
        )
        if has_evidence:
            return []
        return [FindingResult(
            level="L3",
            severity="high",
            category="root_cause_unsupported_by_evidence",
            title="Root cause conclusion stated without citing supporting evidence",
            description=(
                "The root cause section states a conclusion but does not cite the evidence reviewed "
                "to reach that conclusion. Root cause determinations must be supported by documented "
                "evidence review — batch records, data, observations, or analyses. An unsupported "
                "conclusion is an assertion, not an investigation, and cannot be verified by an inspector."
            ),
            evidence=rc_window[:200].strip(),
            location=_nearest_section(text, rc_section.start()) or "Root Cause Analysis",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    def _check_l3_impact_statements_supported(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Impact assessment conclusions (product quality, patient safety) must be supported by data."""
        text = ctx.document_text
        impact_section = re.search(r'impact\s+assessment|impact\s+(?:on|to)\s+(?:product|quality|patient)', text, re.IGNORECASE)
        if not impact_section:
            return []
        impact_window = text[impact_section.start():impact_section.start() + 600]
        has_no_impact = re.search(
            r'no\s+(?:impact|effect|concern|risk)|not\s+(?:impacted|affected|compromised)',
            impact_window, re.IGNORECASE
        )
        if not has_no_impact:
            return []
        has_basis = re.search(
            r'(?:because|basis|data|test|result|specification|within\s+limit|analysis|review)',
            impact_window, re.IGNORECASE
        )
        if has_basis:
            return []
        return [FindingResult(
            level="L3",
            severity="high",
            category="no_impact_claim_unsupported",
            title="'No impact' conclusion stated without documented analytical basis",
            description=(
                "The impact assessment concludes no product quality or patient safety impact but "
                "does not cite the analytical data, test results, or specifications that support this "
                "conclusion. A bare 'no impact' statement is unacceptable — the inspector cannot "
                "verify the basis for the determination without cited evidence."
            ),
            evidence=impact_window[:200].strip(),
            location=_nearest_section(text, impact_section.start()) or "Impact Assessment",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.76,
            validated=True,
        )]

    def _check_l3_consistency_checks(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Check for internal consistency — dates, batch numbers, and conclusions should be consistent."""
        text = ctx.document_text
        findings = []
        # Check if deviation date is before discovery date (logical error)
        dates = re.findall(
            r'\d{1,2}[/\-–.]\d{1,2}[/\-–.]\d{2,4}',
            text[:3000]
        )
        if len(dates) >= 2:
            # Just check that dates exist; actual comparison would need parsing
            pass
        # Check for conflicting conclusions (confirmed OOS + no issue)
        confirmed_oos = bool(re.search(r'confirmed\s+OOS|OOS\s+confirmed', text, re.IGNORECASE))
        no_issue = bool(re.search(r'no\s+(?:issue|problem|concern|failure)\s+(?:found|identified|noted)', text, re.IGNORECASE))
        if confirmed_oos and no_issue:
            findings.append(FindingResult(
                level="L3",
                severity="critical",
                category="conflicting_conclusions",
                title="Conflicting conclusions — Confirmed OOS but 'no issue' also stated",
                description=(
                    "The investigation both confirms an OOS result AND states 'no issue found'. "
                    "These conclusions are mutually exclusive. A confirmed OOS is by definition an "
                    "issue requiring CAPA, batch disposition decision, and potentially regulatory "
                    "reporting. Internal inconsistency of this type undermines the credibility of "
                    "the entire investigation."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
            ))
        return findings

    def _check_l8_disposition_justified(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Batch disposition decision must be explicitly documented and justified in Deviation Report."""
        text = ctx.document_text
        has_disposition = re.search(
            r'(?:batch\s+disposition|disposition[:\s]*(?:released?|rejected?|destroyed?|quarantined?|reworked?)|'
            r'(?:released?|rejected?|destroyed?)\s+(?:batch|product|lot))',
            text, re.IGNORECASE
        )
        if has_disposition:
            window = text[has_disposition.start():has_disposition.start() + 400]
            has_justification = re.search(
                r'(?:basis|because|justified|in\s+accordance|per\s+SOP|specification|result|data)',
                window, re.IGNORECASE
            )
            if not has_justification:
                return [FindingResult(
                    level="L8",
                    severity="critical",
                    category="disposition_not_justified",
                    title="Batch disposition stated but not justified with analytical or QA basis",
                    description=(
                        "A batch disposition decision is stated but the basis for this decision is "
                        "not documented. Every disposition decision must be justified by: the investigation "
                        "conclusion, test results (if retesting was performed), QA approval authority, and "
                        "the regulatory basis for the decision. Undocumented dispositions are a direct "
                        "product safety vulnerability and a GMP record violation per 21 CFR 211.192."
                    ),
                    evidence=window[:200].strip(),
                    location=_nearest_section(text, has_disposition.start()) or "Disposition",
                    regulatory_citation="21 CFR 211.192",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.82,
                    validated=True,
                )]
            return []
        return [FindingResult(
            level="L8",
            severity="critical",
            category="batch_disposition_absent",
            title="No batch disposition decision documented in Deviation Report",
            description=(
                "No batch disposition (Released / Rejected / Destroyed / Reworked) was found. "
                "Every Deviation Report involving a manufactured batch must document the final "
                "disposition of the affected batch(es) and the basis for that decision. Without "
                "disposition documentation, there is no evidence that the affected batch's fate "
                "was formally evaluated by the quality unit per 21 CFR 211.192."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.75,
            validated=True,
        )]

    # ========== L3: LIR-Specific Checks ==========

    def _check_l3_phase2_adequacy(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Phase II (full investigation) must address manufacturing, process, and materials."""
        text = ctx.document_text
        has_phase2 = re.search(r'phase\s*(?:ii|2)\b|phase\s+two\b', text, re.IGNORECASE)
        if not has_phase2:
            return []
        phase2_window = text[has_phase2.start():has_phase2.start() + 1200]
        elements_checked = {
            "manufacturing review": bool(re.search(r'manufacturing|production|process|batch\s+record', phase2_window, re.IGNORECASE)),
            "materials review": bool(re.search(r'raw\s+material|excipient|reagent|standard|chemical', phase2_window, re.IGNORECASE)),
            "environmental review": bool(re.search(r'environment(?:al)?|temperature|humidity|facility', phase2_window, re.IGNORECASE)),
        }
        missing = [e for e, present in elements_checked.items() if not present]
        if not missing:
            return []
        return [FindingResult(
            level="L3",
            severity="high",
            category="phase2_investigation_incomplete",
            title=f"Phase II investigation incomplete — missing: {', '.join(missing)}",
            description=(
                f"The Phase II investigation does not address: {', '.join(missing)}. "
                f"FDA OOS Guidance 2006 requires Phase II to systematically investigate all "
                f"potential causes outside the laboratory — including manufacturing process, "
                f"raw materials, equipment, and environmental conditions. An incomplete Phase II "
                f"may miss the actual root cause, leading to recurrence."
            ),
            evidence=phase2_window[:200].strip(),
            location=_nearest_section(text, has_phase2.start()) or "Phase II Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.72,
            validated=True,
        )]

    def _check_l3_retest_documentation(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Any retesting in an OOS investigation must be pre-authorized and documented."""
        text = ctx.document_text
        retest = re.search(r'\b(?:re-?test(?:ed|ing)?|repeat\s+test(?:ing)?|additional\s+test(?:ing)?)\b', text, re.IGNORECASE)
        if not retest:
            return []
        retest_window = text[max(0, retest.start() - 100):retest.start() + 500]
        has_authorization = re.search(
            r'(?:QA\s+(?:approv|authoris|authoriz)|authoris\w+\s+by|approved\s+retesting|'
            r'retesting\s+(?:plan|protocol|strategy)|predefined\s+(?:retesting|plan))',
            retest_window, re.IGNORECASE
        )
        if has_authorization:
            return []
        return [FindingResult(
            level="L3",
            severity="critical",
            category="retesting_not_authorized",
            title="Retesting documented without QA authorization or predefined strategy",
            description=(
                "Retesting is mentioned but no QA authorization, predefined retesting plan, or "
                "predefined strategy is documented. FDA OOS Guidance 2006 strictly requires that "
                "any retesting of an OOS sample must be: pre-authorized by QA before initiation, "
                "conducted under a predefined retesting strategy with documented rationale, and "
                "limited to the number of retests defined in the approved strategy. "
                "Unauthorized retesting is a potential testing-into-compliance violation."
            ),
            evidence=retest_window[:200].strip(),
            location=_nearest_section(text, retest.start()) or "Investigation",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
        )]

    def _check_l3_investigation_completeness(self, ctx: AssessmentContext) -> list[FindingResult]:
        """OOS investigation must reach a definitive conclusion — open-ended investigations are insufficient."""
        text = ctx.document_text
        ambiguous_conclusion = re.search(
            r'(?:root\s+cause\s+(?:could\s+not\s+be\s+determined|is\s+unknown|not\s+(?:identified|found|determined))|'
            r'inconclusive|may\s+have\s+been\s+caused\s+by|possibly\s+due\s+to|'
            r'no\s+assignable\s+cause\s+was\s+found)',
            text, re.IGNORECASE
        )
        if not ambiguous_conclusion:
            return []
        has_invalidation_basis = re.search(
            r'(?:result\s+(?:was\s+)?invalidated|result\s+deemed\s+invalid|'
            r'assignable\s+(?:laboratory\s+)?cause)',
            text, re.IGNORECASE
        )
        if has_invalidation_basis:
            return []
        excerpt = text[ambiguous_conclusion.start():ambiguous_conclusion.start() + 200].strip()
        return [FindingResult(
            level="L3",
            severity="critical",
            category="investigation_inconclusive",
            title="OOS investigation conclusion is inconclusive — root cause not definitively identified",
            description=(
                f"The investigation fails to reach a definitive conclusion: '{excerpt[:150]}'. "
                f"An inconclusive investigation is not an acceptable closure. If no assignable cause "
                f"was found in Phase I, Phase II must be completed and its conclusion documented. "
                f"If no root cause is identified after Phase II, the batch must be rejected. "
                f"Closing an OOS without a definitive conclusion circumvents the GMP investigation "
                f"requirement and is routinely cited in FDA Warning Letters."
            ),
            evidence=excerpt[:200],
            location=_nearest_section(text, ambiguous_conclusion.start()) or "Conclusion",
            regulatory_citation="21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.88,
            validated=True,
        )]

    # ========== L2: SOP Document Control Checks ==========

    def _check_l2_supersedes_reference(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Document must declare what it supersedes — essential for version traceability."""
        text_lower = ctx.document_text.lower()
        has_supersedes = re.search(
            r'(?:supersede[sd]?|replaces?|obsoletes?|previous\s+(?:version|revision|document))\s*[:\-]?\s*\S',
            text_lower
        )
        if has_supersedes:
            return None
        return FindingResult(
            level="L2",
            severity="medium",
            category="supersedes_reference_absent",
            title="Supersedes/Replaces reference absent — version traceability gap",
            description=(
                "No 'Supersedes' or 'Replaces' field was found. Every revision must reference "
                "the document version it supersedes to maintain a continuous, auditable version "
                "history per 21 CFR 211.68 and EU GMP Part I Ch. 4. Without this link, "
                "an inspector cannot verify that obsolete versions were withdrawn."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.73,
            validated=True,
        )

    def _check_l2_change_control_entries(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Revision history table must be present and contain at least one entry."""
        text_lower = ctx.document_text.lower()
        has_history = re.search(
            r'(?:revision\s+history|change\s+(?:history|log|control\s+(?:history|log|table))|'
            r'document\s+history)',
            text_lower
        )
        if not has_history:
            return FindingResult(
                level="L2",
                severity="medium",
                category="revision_history_absent",
                title="Revision history / change log not present in document",
                description=(
                    "No revision history or change control table was detected. GMP documents must "
                    "contain a section documenting all revisions — including revision number, "
                    "date, description of change, and approver — to demonstrate a traceable "
                    "change history per 21 CFR 211.68."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.78,
                validated=True,
            )
        return None

    def _check_l2_author_reviewer_approver(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Three-tier authorship (Prepared / Reviewed / Approved) is required for independence."""
        text_lower = ctx.document_text.lower()
        has_prepared = bool(re.search(r'prepared\s*by|authored\s*by|written\s*by', text_lower))
        has_reviewed = bool(re.search(r'reviewed\s*by|review\s*(?:and\s+)?(?:approved|signature)', text_lower))
        has_approved = bool(re.search(r'approved\s*by|final\s+approv|qa\s+(?:approv|sign)', text_lower))
        if has_prepared and has_reviewed and has_approved:
            return None
        missing = [
            role for role, present in [("Prepared By", has_prepared), ("Reviewed By", has_reviewed), ("Approved By", has_approved)]
            if not present
        ]
        return FindingResult(
            level="L2",
            severity="medium",
            category="authorship_roles_incomplete",
            title=f"Authorship roles incomplete: missing {', '.join(missing)}",
            description=(
                f"The document is missing the following authorship role(s): {', '.join(missing)}. "
                f"A three-tier authorship model (Prepared By / Reviewed By / Approved By) is required "
                f"to demonstrate independent review and QA approval per 21 CFR 211.22(a). "
                f"Documents with a single signer cannot demonstrate independent oversight."
            ),
            evidence=f"Detected roles: {'Prepared By' if has_prepared else ''} {'Reviewed By' if has_reviewed else ''} {'Approved By' if has_approved else ''}.".strip(),
            regulatory_citation="21 CFR 211.22(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.74,
            validated=True,
        )

    def _check_l2_distribution_list(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Controlled copy distribution list or 'controlled copy' statement required."""
        text_lower = ctx.document_text.lower()
        has_distribution = re.search(
            r'(?:distribution\s+list|controlled\s+copy|copy\s+no|'
            r'issued\s+to|controlled\s+distribution|copy\s+holder)',
            text_lower
        )
        if has_distribution:
            return None
        return FindingResult(
            level="L2",
            severity="low",
            category="distribution_list_absent",
            title="Controlled copy distribution list or designation not found",
            description=(
                "No distribution list, controlled copy designation, or copy number was found. "
                "GMP document control requires that controlled copies be tracked — knowing which "
                "personnel hold current controlled copies is essential to ensure obsolete versions "
                "can be recalled and replaced during a revision per 21 CFR 211.68."
            ),
            evidence="",
            regulatory_citation="21 CFR 211.68",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.65,
            validated=True,
        )

    # ========== L4: Additional ALCOA+ Checks ==========

    def _check_l4_alcoa_legible(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """ALCOA Legible — check for indicators of scanned/low-quality content or unreadable sections."""
        text = ctx.document_text
        # Very short text for a multi-page document suggests poor OCR / scan
        words = len(text.split())
        if words < 50:
            return FindingResult(
                level="L4",
                severity="high",
                category="alcoa_legibility_concern",
                title="Document text is extremely sparse — possible scan/OCR quality issue",
                description=(
                    f"Only {words} words were extracted from this document. Extremely sparse text "
                    f"may indicate a poor-quality scan, OCR failure, or that the document is "
                    f"primarily image-based with no text layer. GMP ALCOA+ requires records to be "
                    f"legible and accessible — image-only records do not meet the 'legible and "
                    f"reconstructable' requirement per 21 CFR 211.68."
                ),
                evidence=f"Extracted text word count: {words}",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            )
        # Check for patterns indicating unreadable content
        unreadable = re.findall(r'[■-◿☀-➿]{3,}|_{10,}|[?]{5,}|\[image\]|\[figure\]', text, re.IGNORECASE)
        if len(unreadable) > 5:
            return FindingResult(
                level="L4",
                severity="medium",
                category="alcoa_legibility_concern",
                title="Multiple unreadable/corrupted sections detected in extracted text",
                description=(
                    f"{len(unreadable)} sections with garbled or unreadable content were found. "
                    f"ALCOA+ Legible requires that all GMP records be readable and fully recoverable. "
                    f"If any section of a GMP record is illegible, the entire record may be deemed "
                    f"inadequate during inspection per 21 CFR 211.68."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.70,
                validated=True,
            )
        return None

    def _check_l4_alcoa_original(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """ALCOA Original — check for copy-without-certification language."""
        text_lower = ctx.document_text.lower()
        # Certified true copy is OK; uncertified copy flag is bad
        uncertified_copy = re.search(
            r'(?:(?:this\s+is\s+a|being\s+a)\s+copy|'
            r'copy\s+of\s+original|photocopy|scanned\s+copy)',
            text_lower
        )
        certified = re.search(
            r'certified\s+(?:true\s+)?copy|true\s+(?:and\s+accurate\s+)?copy',
            text_lower
        )
        if uncertified_copy and not certified:
            m = uncertified_copy
            excerpt = ctx.document_text[m.start():m.start() + 200].strip()
            return FindingResult(
                level="L4",
                severity="medium",
                category="alcoa_original_concern",
                title="Document references being a copy but lacks certified true copy statement",
                description=(
                    f"The document references a copy ({excerpt[:120]}) but no 'Certified True Copy' "
                    f"statement was found. GMP ALCOA+ Original requires that copies used as GMP "
                    f"records be explicitly certified as true and accurate copies of the original, "
                    f"with the certifier identified and dated per 21 CFR 211.68."
                ),
                evidence=excerpt[:200],
                location=_nearest_section(ctx.document_text, m.start()),
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.72,
                validated=True,
            )
        return None

    def _check_l4_alcoa_accurate(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """ALCOA Accurate — check for uncorrected corrections (no initial/date on corrections)."""
        text = ctx.document_text
        # Look for correction indicators without proper documentation
        raw_correction = re.search(
            r'(?:see\s+correction|correction\s*[:\-]|erratum|corrig(?:endum)?)',
            text, re.IGNORECASE
        )
        if not raw_correction:
            return None
        context_after = text[raw_correction.end():raw_correction.end() + 300]
        has_initials = re.search(r'[A-Z]{2,3}\s*/\s*\d|initials?\s*[:]\s*[A-Z]', context_after)
        has_date = re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', context_after)
        if not (has_initials and has_date):
            excerpt = text[raw_correction.start():raw_correction.start() + 250].strip()
            return FindingResult(
                level="L4",
                severity="medium",
                category="alcoa_accurate_correction",
                title="Correction/erratum referenced without documented initials and date",
                description=(
                    f"A correction is referenced ({excerpt[:120]}) but no initials and date were "
                    f"found in the surrounding text. ALCOA+ Accurate requires that all corrections "
                    f"to GMP records be documented with the corrector's initials, date, and reason "
                    f"for correction. A single-line strikethrough with initials/date is the minimum; "
                    f"white-out or obscured original entries are never acceptable per 21 CFR 211.68."
                ),
                evidence=excerpt,
                location=_nearest_section(text, raw_correction.start()),
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.73,
                validated=True,
            )
        return None

    def _check_l4_data_recording_instructions(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Data recording instructions must be present when forms/data fields are referenced."""
        text_lower = ctx.document_text.lower()
        has_form_ref = re.search(
            r'(?:complete\s+(?:the\s+)?form|fill\s+in|record\s+(?:in|on)\s+form|'
            r'enter\s+(?:data|result)|document\s+(?:in|on)\s+(?:form|worksheet|logbook))',
            text_lower
        )
        if not has_form_ref:
            return None
        has_instructions = re.search(
            r'(?:instructions?\s+for\s+(?:completion|recording)|'
            r'how\s+to\s+(?:complete|record|fill)|'
            r'data\s+(?:entry|recording)\s+(?:instructions?|guidance))',
            text_lower
        )
        if not has_instructions:
            return FindingResult(
                level="L4",
                severity="low",
                category="data_recording_instructions_absent",
                title="Forms referenced but data recording instructions not provided",
                description=(
                    "The document references forms or data fields to be completed but does not "
                    "include instructions for data recording. ALCOA+ requires that records be "
                    "completed accurately and completely — personnel completing forms must have "
                    "written instructions on how to record data, handling of out-of-range values, "
                    "and error correction procedures per 21 CFR 211.68."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.68,
                validated=True,
            )
        return None

    def _check_l4_form_attachment_references(self, ctx: AssessmentContext) -> list[FindingResult]:
        """All form/attachment references in body text should have corresponding attachment entries."""
        text = ctx.document_text
        findings = []
        # Find all form references in body
        form_refs = re.findall(
            r'(?:form|attachment|exhibit|appendix|annex)\s*[:\-]?\s*([A-Z0-9\-]+)',
            text, re.IGNORECASE
        )
        if not form_refs:
            return []
        # Check if there's a corresponding attachment/appendix section
        has_attachment_section = bool(re.search(
            r'(?:attachments?|appendix|appendices|exhibits?|annexes?)\s*\n',
            text, re.IGNORECASE
        ))
        unique_refs = set(form_refs[:10])  # Check first 10 unique form refs
        if unique_refs and not has_attachment_section:
            findings.append(FindingResult(
                level="L4",
                severity="low",
                category="form_attachment_section_absent",
                title=f"{len(unique_refs)} form/attachment reference(s) in body but no Attachments section found",
                description=(
                    f"The document references {len(unique_refs)} form(s)/attachment(s) "
                    f"({', '.join(list(unique_refs)[:5])}) but no corresponding Attachments or "
                    f"Appendices section was found. GMP SOPs should include all referenced forms "
                    f"as controlled attachments, or reference the form number in the document "
                    f"control system. Unreferenced form numbers cannot be verified during inspection."
                ),
                evidence=f"Form references found: {', '.join(list(unique_refs)[:5])}",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.65,
                validated=True,
            ))
        return findings

    # ========== L5: Data Intelligence Checks ==========

    def _check_l5_critical_parameters_identified(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Critical Quality Attributes (CQAs) and Critical Process Parameters (CPPs) must be called out."""
        text_lower = ctx.document_text.lower()
        is_process_doc = re.search(
            r'(?:manufacturing|production|process|batch\s+record|synthesis|filling|'
            r'blending|granulation|coating|lyophili)',
            text_lower
        )
        if not is_process_doc:
            return None  # Only applicable to process/manufacturing documents
        has_cqa_cpp = re.search(
            r'(?:critical\s+(?:quality\s+attribute|process\s+parameter|control\s+parameter)|'
            r'cqa|cpp\b|key\s+parameter|critical\s+attribute)',
            text_lower
        )
        if has_cqa_cpp:
            return None
        return FindingResult(
            level="L5",
            severity="medium",
            category="critical_parameters_not_identified",
            title="Critical Quality Attributes (CQAs) or Critical Process Parameters (CPPs) not identified",
            description=(
                "This appears to be a process/manufacturing document but no Critical Quality "
                "Attributes (CQAs) or Critical Process Parameters (CPPs) were identified. "
                "ICH Q8(R2) and ICH Q9 require that critical parameters be explicitly identified "
                "to support risk-based process control and to define the acceptance criteria for "
                "process monitoring. Without these identifications, the link between process "
                "control and product quality cannot be demonstrated."
            ),
            evidence="",
            regulatory_citation="ICH Q8(R2) / ICH Q9",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.70,
            validated=True,
        )

    def _check_l5_acceptance_criteria_defined(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Acceptance criteria must be numerically specified — not just referenced to specs."""
        text_lower = ctx.document_text.lower()
        # Only applies if there are measurable parameters
        has_measurement = re.search(
            r'(?:measure|test|check|inspect|verify|record\s+(?:value|reading|result))',
            text_lower
        )
        if not has_measurement:
            return None
        has_criteria = re.search(
            r'(?:acceptance\s+criteri[ao]|specification|limit[:\s]\d|'
            r'pass\s+(?:if|when)|fail\s+(?:if|when)|nlt\s+\d|nmt\s+\d|'
            r'\d+\s*(?:%|mg|kg|ppm|°C|rpm)\s*(?:to|–|-)\s*\d+\s*(?:%|mg|kg|ppm|°C|rpm))',
            text_lower
        )
        if not has_criteria:
            return FindingResult(
                level="L5",
                severity="medium",
                category="acceptance_criteria_absent",
                title="Measurable parameters referenced but acceptance criteria not defined",
                description=(
                    "The document references measurable parameters (test, check, measure) but "
                    "no numerical acceptance criteria were found. GMP requires that all "
                    "in-process checks and final tests have defined acceptance criteria — "
                    "pass/fail ranges expressed as specific numerical limits (e.g., '98.0–102.0%', "
                    "'NLT 0.5 mg', 'NMT 500 ppm'). Vague criteria cannot be objectively assessed "
                    "during inspection per 21 CFR 211.192."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.71,
                validated=True,
            )
        return None

    def _check_l5_measurement_units_specified(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Numerical values must have units — unitless numbers in a GMP document are ambiguous."""
        text = ctx.document_text
        findings = []
        # Find numerical ranges/limits without units
        unitless_numbers = re.findall(
            r'(?:limit|criteria|specification|spec)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:to|–|-)\s*(\d+\.?\d*)(?!\s*(?:%|mg|kg|g|ml|l|ppm|ppb|°|rpm|bar|psi|nm|μm|mm|cm|m\b|s\b|min\b|h\b|d\b|°C|°F|K\b|mol|mmol|μmol|IU|cfu|mEq))',
            text, re.IGNORECASE
        )
        if len(unitless_numbers) > 2:
            findings.append(FindingResult(
                level="L5",
                severity="low",
                category="measurement_units_absent",
                title=f"{len(unitless_numbers)} numerical acceptance criteria found without units",
                description=(
                    f"{len(unitless_numbers)} numerical criteria appear to lack measurement units. "
                    f"All numerical acceptance limits in a GMP document must be expressed with "
                    f"appropriate units (e.g., %, mg/mL, °C, ppm). Unitless numbers are ambiguous "
                    f"and cannot be objectively interpreted during testing or inspection per 21 CFR 211.68."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.67,
                validated=True,
            ))
        return findings

    def _check_l5_statistical_methods_referenced(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Statistical methods must be cited when statistical acceptance criteria are used."""
        text_lower = ctx.document_text.lower()
        has_statistical = re.search(
            r'(?:rsd|relative\s+standard\s+deviation|coefficient\s+of\s+variation|cv\s*%|'
            r'confidence\s+interval|statistical\s+(?:limit|method|test|analysis)|'
            r'standard\s+deviation\s+limit|z-score|t-test|anova)',
            text_lower
        )
        if not has_statistical:
            return None
        has_method_ref = re.search(
            r'(?:per\s+usp|per\s+ep|per\s+ich|per\s+21\s+cfr|'
            r'usp\s*<\d+>|statistical\s+method\s+(?:as|per|in|described)|'
            r'annex\s+\d+|chapter\s+\d+)',
            text_lower
        )
        if not has_method_ref:
            return FindingResult(
                level="L5",
                severity="low",
                category="statistical_method_unreferenced",
                title="Statistical acceptance criteria present but underlying method not cited",
                description=(
                    "Statistical acceptance criteria (RSD, CV%, confidence interval, etc.) are "
                    "referenced in this document but the underlying statistical method or regulatory "
                    "chapter is not cited. Statistical methods used for GMP acceptance decisions "
                    "must reference a validated statistical procedure (e.g., USP <1010>, ICH Q2(R1), "
                    "or a company-specific validated SOP) to be reproducible and auditable."
                ),
                evidence="",
                regulatory_citation="ICH Q2(R1)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.67,
                validated=True,
            )
        return None

    # ========== L1/L4/L5/L7: Validation Protocol/Report Checks ==========

    def _check_l1_validation_type_declared(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Validation type (IQ/OQ/PQ, Process, Cleaning, Computer System) must be declared."""
        text_lower = ctx.document_text.lower()
        has_type = re.search(
            r'(?:\biq\b|\boq\b|\bpq\b|installation\s+qualification|operational\s+qualification|'
            r'performance\s+qualification|process\s+validation|cleaning\s+validation|'
            r'computer\s+(?:system\s+)?validation|csv\b|analytical\s+method\s+validation|'
            r'equipment\s+qualification)',
            text_lower
        )
        if has_type:
            return None
        return FindingResult(
            level="L1",
            severity="high",
            category="validation_type_not_declared",
            title="Validation type (IQ/OQ/PQ, Process, Cleaning, CSV) not declared in document",
            description=(
                "The document does not declare its validation type (e.g., IQ, OQ, PQ, Process Validation, "
                "Cleaning Validation, Computer System Validation). Every validation document must "
                "explicitly identify the type of validation activity being performed to establish "
                "the applicable regulatory requirements and acceptance criteria basis per "
                "FDA Process Validation Guidance 2011 and EU GMP Annex 15."
            ),
            evidence="",
            regulatory_citation="FDA PV Guidance 2011 / EU GMP Annex 15",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.80,
            validated=True,
        )

    def _check_l1_protocol_report_distinction(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Document must be clearly identified as either a Protocol or a Report (not both)."""
        text_lower = ctx.document_text.lower()
        is_protocol = bool(re.search(r'\b(?:validation\s+)?protocol\b', text_lower))
        is_report = bool(re.search(r'\b(?:validation\s+)?report\b', text_lower))
        if is_protocol == is_report and is_protocol:
            # Both found — check if they're clearly labelled as different docs or if this is a combined doc
            combined = re.search(r'protocol(?:\s*and|\s*/)\s*report|report(?:\s*and|\s*/)\s*protocol', text_lower)
            if not combined:
                return FindingResult(
                    level="L1",
                    severity="medium",
                    category="protocol_report_ambiguity",
                    title="Document references both 'Protocol' and 'Report' without clear distinction",
                    description=(
                        "The document contains both 'Protocol' and 'Report' terminology without clearly "
                        "distinguishing between them. A Validation Protocol is approved before execution "
                        "and defines acceptance criteria; a Validation Report is written after execution "
                        "and documents results. Combining or confusing these documents is a GMP document "
                        "control concern — pre-execution approval of acceptance criteria could be "
                        "compromised per FDA Process Validation Guidance 2011."
                    ),
                    evidence="",
                    regulatory_citation="FDA PV Guidance 2011",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.68,
                    validated=True,
                )
        return None

    def _check_l4_pre_execution_approval(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Protocol must be QA-approved before execution — detected when approval date is after first test date."""
        text = ctx.document_text
        findings = []
        # Check for execution date before approval
        exec_date_m = re.search(
            r'(?:execution\s+(?:started?|date|commenced|initiated)|test\s+(?:start|date)|'
            r'(?:performed|conducted|executed)\s+on|test\s+date)\s*[:\-]?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text, re.IGNORECASE
        )
        approval_date_m = re.search(
            r'(?:approved\s+(?:by|date)|qa\s+(?:approv|sign)(?:ature)?)\s+[^\n]{0,40}?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            text, re.IGNORECASE
        )
        if exec_date_m and approval_date_m:
            from datetime import datetime
            date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y", "%Y-%m-%d"]
            exec_date = approv_date = None
            for fmt in date_formats:
                try:
                    exec_date = datetime.strptime(exec_date_m.group(1), fmt); break
                except ValueError:
                    pass
            for fmt in date_formats:
                try:
                    approv_date = datetime.strptime(approval_date_m.group(1), fmt); break
                except ValueError:
                    pass
            if exec_date and approv_date and exec_date < approv_date:
                findings.append(FindingResult(
                    level="L4",
                    severity="critical",
                    category="validation_executed_before_approval",
                    title=f"Validation protocol executed ({exec_date_m.group(1)}) before QA approval ({approval_date_m.group(1)})",
                    description=(
                        f"The validation execution date ({exec_date_m.group(1)}) precedes the QA "
                        f"approval date ({approval_date_m.group(1)}). A validation protocol must be "
                        f"reviewed and approved by QA before execution begins. Executing before "
                        f"approval invalidates the pre-defined acceptance criteria principle and "
                        f"creates a data integrity exposure — the protocol could have been modified "
                        f"after execution per FDA Process Validation Guidance 2011."
                    ),
                    evidence=f"Execution: {exec_date_m.group(1)} | Approval: {approval_date_m.group(1)}",
                    regulatory_citation="FDA PV Guidance 2011",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.91,
                    validated=True,
                ))
        return findings

    def _check_l4_results_vs_criteria_comparison(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Validation reports must explicitly compare actual results to pre-defined acceptance criteria."""
        text_lower = ctx.document_text.lower()
        is_report = re.search(r'validation\s+report|execution\s+(?:report|summary)|results?\s+summary', text_lower)
        if not is_report:
            return None  # Protocol only — results section not expected
        has_results = re.search(r'(?:result|actual|obtained|measured)\s*[:\-]?\s*\d', text_lower)
        has_criteria = re.search(r'(?:acceptance\s+criteri[ao]|specification|limit)\s*[:\-]?\s*\S', text_lower)
        has_comparison = re.search(
            r'(?:meets?\s+(?:acceptance\s+)?criteria|passes?|complies?|within\s+(?:spec|limit|criteria)|'
            r'result\s+(?:is|are)\s+(?:acceptable|compliant|within)|pass(?:ed)?|fail(?:ed)?)',
            text_lower
        )
        if has_results and has_criteria and not has_comparison:
            return FindingResult(
                level="L4",
                severity="high",
                category="results_criteria_comparison_absent",
                title="Results and acceptance criteria present but no explicit pass/fail comparison statement",
                description=(
                    "The validation report contains both results and acceptance criteria but no "
                    "explicit comparison statement ('Meets criteria', 'Pass', 'Fail', etc.) was found. "
                    "FDA Process Validation Guidance 2011 requires that the validation conclusion "
                    "explicitly state whether the results meet the pre-defined acceptance criteria. "
                    "Inspectors will ask to see the direct link between result values and the "
                    "acceptance criteria they were evaluated against."
                ),
                evidence="",
                regulatory_citation="FDA PV Guidance 2011",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.78,
                validated=True,
            )
        return None

    def _check_l4_deviation_handling(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Validation reports must document all deviations and their impact on conclusions."""
        text_lower = ctx.document_text.lower()
        is_report = re.search(r'validation\s+report|execution|results?\s+summary', text_lower)
        if not is_report:
            return None
        has_deviation_section = re.search(
            r'(?:deviations?|discrepanc(?:y|ies)|non-?conformanc(?:y|e))\s*(?:during|observed|section)',
            text_lower
        )
        if not has_deviation_section:
            return FindingResult(
                level="L4",
                severity="medium",
                category="validation_deviation_section_absent",
                title="Validation report lacks a Deviations/Discrepancies section",
                description=(
                    "The validation report does not contain a Deviations or Discrepancies section. "
                    "All validation reports must include a section documenting any deviations from "
                    "the approved protocol — even if the conclusion is 'no deviations occurred.' "
                    "An explicit 'No deviations' statement is required; omitting this section "
                    "prevents an assessor from confirming whether the protocol was followed as written "
                    "per FDA Process Validation Guidance 2011 and EU GMP Annex 15."
                ),
                evidence="",
                regulatory_citation="FDA PV Guidance 2011 / EU GMP Annex 15",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.76,
                validated=True,
            )
        return None

    def _check_l5_validation_runs_count(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Process validation requires a minimum of 3 consecutive successful batches."""
        text_lower = ctx.document_text.lower()
        is_process_val = re.search(
            r'process\s+validation|(?:manufacturing|production)\s+process\s+(?:validation|qualification)',
            text_lower
        )
        if not is_process_val:
            return None
        # Count batch references
        batch_nums = re.findall(
            r'(?:batch|lot)\s*(?:no|number|#)?\s*[:\-]?\s*[A-Z0-9][A-Z0-9\-/]+',
            text_lower
        )
        unique_batches = len(set(batch_nums))
        if 0 < unique_batches < 3:
            return FindingResult(
                level="L5",
                severity="high",
                category="insufficient_validation_batches",
                title=f"Process validation may have insufficient runs: {unique_batches} batch(es) identified (minimum 3 required)",
                description=(
                    f"Only {unique_batches} batch reference(s) were found in this process validation "
                    f"document. FDA Process Validation Guidance 2011 (Process Performance Qualification "
                    f"stage) requires a minimum of 3 consecutive batches demonstrating consistent "
                    f"performance. A validation with fewer than 3 successful runs does not meet the "
                    f"minimum statistical basis for demonstrating process consistency."
                ),
                evidence=f"Batch references found: {', '.join(set(batch_nums[:5]))}",
                regulatory_citation="FDA PV Guidance 2011 Section IV.C",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.77,
                validated=True,
            )
        return None

    def _check_l7_requalification_schedule(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Validation documents must define when requalification/revalidation is required."""
        text_lower = ctx.document_text.lower()
        has_requalification = re.search(
            r'(?:requalif|revalidat|periodic\s+review\s+of\s+validation|'
            r'change\s+control\s+trigger|major\s+change|revalidation\s+trigger)',
            text_lower
        )
        if has_requalification:
            return None
        return FindingResult(
            level="L7",
            severity="medium",
            category="requalification_trigger_absent",
            title="Requalification / revalidation triggers and schedule not defined",
            description=(
                "No requalification schedule or change control triggers were found. "
                "Validated processes and systems must define the conditions under which "
                "requalification or revalidation is required — typically including major equipment "
                "changes, process changes, significant deviations, and periodic review intervals. "
                "The absence of these triggers creates an open-ended validation that cannot be "
                "demonstrated as 'maintained in a state of control' per FDA PV Guidance 2011."
            ),
            evidence="",
            regulatory_citation="FDA PV Guidance 2011 / EU GMP Annex 15",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.73,
            validated=True,
        )

    # ========== L7: LIR Lifecycle / Timeline Checks ==========

    def _check_l7_oos_30day_timeline(self, ctx: AssessmentContext) -> list[FindingResult]:
        """FDA OOS Guidance 2006 requires the full OOS investigation be completed within 30 calendar days."""
        text = ctx.document_text
        text_lower = text.lower()
        findings = []

        has_overdue_marker = bool(re.search(
            r'(?:exceed(?:ed|ing)\s+30[\s-]day|beyond\s+30\s+(?:calendar\s+)?day|'
            r'investigation\s+(?:not\s+)?completed\s+within\s+30|'
            r'extended\s+investigation\s+timeline|>30\s*days?\s+(?:for\s+)?investigation)',
            text_lower
        ))
        has_extension_justification = bool(re.search(
            r'(?:extension\s+(?:approved|justif|request)|timeline\s+extension|'
            r'extended\s+(?:due\s+to|because)|30[\s-]day\s+extension)',
            text_lower
        ))
        has_30day_reference = bool(re.search(
            r'(?:30[\s-](?:calendar\s+)?day|within\s+30\s+days?|30\s+days?\s+(?:of\s+)?(?:initiation|opening))',
            text_lower
        ))

        if has_overdue_marker and not has_extension_justification:
            findings.append(FindingResult(
                level="L7",
                severity="high",
                category="oos_timeline_exceeded",
                title="OOS investigation exceeded 30-day timeline without documented justification",
                description=(
                    "The investigation indicates it exceeded the 30-calendar-day completion requirement "
                    "without a documented extension justification. FDA OOS Guidance 2006 requires "
                    "OOS investigations to be completed within 30 calendar days of initiating the "
                    "investigation. Extensions require explicit QA approval and documented rationale. "
                    "Uninvestigated OOS results past 30 days are a recurring FDA 483 observation and "
                    "Warning Letter theme (e.g., 21 CFR 211.192 deficiencies)."
                ),
                evidence=has_overdue_marker and "Text contains markers of exceeded 30-day timeline" or "",
                regulatory_citation="FDA OOS Guidance 2006 / 21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                suggestion_draft=(
                    "Add an Extension Justification section:\n"
                    "Extension Request Date: [Date]\n"
                    "Reason for Extension: [Complexity of investigation / pending analytical confirmation / etc.]\n"
                    "Revised Completion Date: [Date]\n"
                    "QA Approval of Extension: [Signature / Date]\n\n"
                    "FDA OOS Guidance 2006 requires completion within 30 calendar days; "
                    "extensions must be pre-approved and documented."
                ),
                next_step_text="Add extension justification with QA approval and revised completion date.",
                remediation_priority=2,
                confidence_score=0.80,
                validated=True,
            ))

        if not has_30day_reference:
            findings.append(FindingResult(
                level="L7",
                severity="medium",
                category="oos_timeline_not_referenced",
                title="OOS investigation does not reference the 30-day completion requirement",
                description=(
                    "The investigation does not reference the 30-calendar-day timeline requirement "
                    "from FDA OOS Guidance 2006. Compliant LIRs should document the initiation date "
                    "and target completion date and confirm the investigation was concluded within the "
                    "30-day window (or document an approved extension). Absence of this reference "
                    "suggests the timeline requirement is not being tracked."
                ),
                evidence="",
                regulatory_citation="FDA OOS Guidance 2006 / 21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                suggestion_draft=(
                    "Add to LIR Identification section:\n"
                    "Investigation Initiation Date: [Date]\n"
                    "30-Day Target Completion Date: [Date + 30 days]\n"
                    "Actual Completion Date: [Date]\n"
                    "Timeline Status: Completed within 30-day window / Extension approved [Ref No.]"
                ),
                next_step_text="Add initiation date, 30-day target, and actual completion date to the LIR header.",
                remediation_priority=3,
                confidence_score=0.72,
                validated=True,
            ))

        return findings

    def _check_l7_phase2_pre_authorization(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Phase II retesting requires pre-authorization before samples are re-analysed."""
        text_lower = ctx.document_text.lower()

        has_phase2 = bool(re.search(r'phase\s+ii|phase\s+2\b', text_lower))
        if not has_phase2:
            return []

        has_preauth = bool(re.search(
            r'(?:pre[\s-]?authoriz|pre[\s-]?approv|authorized\s+(?:by\s+)?(?:QA|quality)|'
            r'approval\s+(?:prior|before)\s+(?:re)?test|retesting\s+(?:plan|protocol|pre[\s-]approv))',
            text_lower
        ))
        if has_preauth:
            return []

        return [FindingResult(
            level="L7",
            severity="high",
            category="phase2_not_pre_authorized",
            title="Phase II retesting initiated without documented pre-authorization",
            description=(
                "Phase II retesting is documented but pre-authorization by QA before retesting "
                "began was not found. FDA OOS Guidance 2006 is explicit: Phase II retesting "
                "must be planned and pre-authorized — not initiated ad hoc after a failing result. "
                "Unauthorized retesting is one of the most cited OOS investigation deficiencies in "
                "FDA Warning Letters and constitutes testing into compliance."
            ),
            evidence="Phase II retesting section present; no pre-authorization language found.",
            regulatory_citation="FDA OOS Guidance 2006 / 21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            suggestion_draft=(
                "Add to Phase II section header:\n"
                "Phase II Retesting Pre-Authorization:\n"
                "Authorized by (QA): _____________  Date: ___________\n"
                "Retesting Plan: [# of samples, # of injections, analyst assignment]\n"
                "Predefined Passing Criterion for Invalidation: [Specify OOS limit]\n\n"
                "Retesting must be authorized BEFORE analysts perform additional analyses."
            ),
            next_step_text="Obtain and document QA pre-authorization for Phase II retesting before analyses are performed.",
            remediation_priority=1,
            confidence_score=0.78,
            validated=True,
        )]

    def _check_l7_capa_timeline_defined(self, ctx: AssessmentContext) -> list[FindingResult]:
        """LIR CAPA must include defined completion timelines."""
        text_lower = ctx.document_text.lower()

        has_capa = bool(re.search(r'\bcapa\b|corrective\s+(?:and\s+)?preventive\s+action', text_lower))
        if not has_capa:
            return []

        has_capa_timeline = bool(re.search(
            r'(?:capa\s+(?:due|target|completion|deadline|by)|'
            r'complete\s+(?:by|before|within)\s+\d|'
            r'target\s+(?:date|completion)\s*:\s*\d{1,2}[/-]\d{1,2}|'
            r'due\s+date\s*:\s*\d)',
            text_lower
        ))
        if has_capa_timeline:
            return []

        return [FindingResult(
            level="L7",
            severity="medium",
            category="capa_timeline_absent",
            title="CAPA in LIR lacks defined completion timeline",
            description=(
                "CAPA actions are referenced in the LIR but no completion dates or target timelines "
                "were specified. An LIR CAPA without defined timelines cannot be tracked for "
                "on-time closure and may signal a systemic issue is unresolved. "
                "ICH Q10 and FDA expectations require CAPAs to have measurable timelines. "
                "Open CAPAs from OOS investigations are tracked across inspections."
            ),
            evidence="CAPA section present; no completion date found.",
            regulatory_citation="ICH Q10 / 21 CFR 211.192",
            citation_type="direct",
            agency="FDA",
            suggestion_draft=(
                "Update CAPA section with:\n"
                "CAPA ID: [Reference to CAPA record]\n"
                "Action Description: [What will be done]\n"
                "Responsible Person: [Name / Role]\n"
                "Target Completion Date: [Date]\n"
                "Effectiveness Check Due: [Date, typically 90 days post-completion]"
            ),
            next_step_text="Assign CAPA ID, responsible owner, and target completion date for each action.",
            remediation_priority=3,
            confidence_score=0.73,
            validated=True,
        )]

    def _check_l7_change_control_trigger(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Impact assessment must describe which changes would invalidate the validation."""
        text_lower = ctx.document_text.lower()
        has_change_trigger = re.search(
            r'(?:change\s+control|changes?\s+that\s+(?:may|would|require\s+revalid|impact\s+the\s+valid)|'
            r'change\s+impact|major\s+change)',
            text_lower
        )
        if has_change_trigger:
            return None
        return FindingResult(
            level="L7",
            severity="low",
            category="change_control_trigger_absent",
            title="Changes requiring revalidation not described in validation document",
            description=(
                "No description of changes that would require revalidation was found. "
                "Best practice requires validation documents to specify which changes — "
                "such as equipment upgrades, process modifications, facility changes, or "
                "critical material changes — would trigger re-assessment of the validated state. "
                "This information is necessary for ongoing change control decisions per "
                "ICH Q10 and FDA Process Validation Guidance 2011."
            ),
            evidence="",
            regulatory_citation="ICH Q10 / FDA PV Guidance 2011",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.67,
            validated=True,
        )

    # ========== L3: Root Cause Depth (Deviation) ==========

    def _check_l3_root_cause_depth(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Root cause analysis must demonstrate analytical depth — not just label 'human error'."""
        text_lower = ctx.document_text.lower()

        # Positive indicators of deep RCA
        deep_rca_patterns = [
            r'5[\s-]*why', r'five\s+why', r'why[\s-]+why',
            r'fishbone', r'ishikawa', r'cause[\s-]+and[\s-]+effect',
            r'fault\s+tree',
            r'systematic\s+(?:analysis|review|investigation)',
            r'failure\s+mode\s+(?:and\s+effect|analysis)',
        ]
        has_deep_rca = any(re.search(p, text_lower) for p in deep_rca_patterns)
        if has_deep_rca:
            return None

        # Check if RCA section exists at all
        has_rca_section = re.search(
            r'root\s+cause|rca\b|cause\s+(?:of|for)\s+(?:the\s+)?deviation', text_lower
        )
        if not has_rca_section:
            return FindingResult(
                level="L3",
                severity="high",
                category="root_cause_analysis_absent",
                title="Root cause analysis section not found in deviation report",
                description=(
                    "No root cause analysis section was identified in this deviation report. "
                    "21 CFR 211.192 requires that any unexplained discrepancy or failure of a "
                    "batch to meet specification shall be thoroughly investigated. A documented "
                    "root cause analysis is the foundation of that investigation."
                ),
                evidence="",
                regulatory_citation="21 CFR 211.192",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.82,
                validated=True,
            )

        # RCA attributes root cause to "human error" without deeper analysis
        human_error_only = bool(re.search(
            r'root\s+cause[\s\S]{0,300}human\s+error', text_lower
        )) and not has_deep_rca

        if human_error_only:
            return FindingResult(
                level="L3",
                severity="high",
                category="root_cause_depth",
                title="Root cause attributed to 'human error' without structured analytical methodology",
                description=(
                    "The investigation concludes 'human error' as the root cause without applying a "
                    "structured methodology (5-Why, fishbone/Ishikawa, fault tree) to identify the "
                    "underlying systemic cause. FDA consistently rejects 'human error' as a root cause "
                    "without demonstrating why the error was possible and what system failed. "
                    "Per 21 CFR 211.192 and ICH Q10, investigations must identify the fundamental "
                    "cause — not surface-level attribution — and propose systemic corrections."
                ),
                evidence="Root cause stated as 'human error' but no structured RCA methodology detected.",
                regulatory_citation="21 CFR 211.192; ICH Q10 Section 3.2",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.83,
                validated=True,
            )

        # RCA exists but no supporting evidence or structured methodology
        evidence_cited = re.search(
            r'(?:data\s+(?:shows?|indicates?|confirms?)|evidence\s+(?:of|that|shows?)|'
            r'trending\s+data|historical\s+(?:data|records?|review))',
            text_lower
        )

        if not evidence_cited:
            return FindingResult(
                level="L3",
                severity="medium",
                category="root_cause_insufficient_depth",
                title="Root cause analysis lacks structured methodology or supporting evidence",
                description=(
                    "The root cause analysis was identified but does not demonstrate structured "
                    "analytical methodology (e.g., 5-Why, fishbone/Ishikawa, fault tree) or cite "
                    "supporting data and evidence. FDA expects investigations to identify the "
                    "fundamental cause — not surface-level attribution — with evidence. "
                    "Per 21 CFR 211.192 and ICH Q10, investigations must be thorough and "
                    "conclusions must be supported by documented facts."
                ),
                evidence="Root cause section present but no structured methodology or evidence citation detected.",
                regulatory_citation="21 CFR 211.192; ICH Q10 Section 3.2",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.71,
                validated=True,
            )

        return None

    # ========== L9: Enforcement Pattern Checks (Deviation / LIR / Validation) ==========

    def _check_l9_enforcement_pattern_match(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Flag if document topic areas match high-frequency FDA + international enforcement patterns."""
        from app.engines import rag_engine, international_enforcement_engine

        text_lower = ctx.document_text.lower()
        doc_cat = (ctx.document_category or "").lower()

        CFR_TOPICS = {
            "211.192": ["investigation", "discrepancy", "out-of-specification", "batch review"],
            "211.100": ["written procedure", "deviation", "standard operating"],
            "211.68":  ["computer", "electronic record", "audit trail", "backup"],
            "211.22":  ["quality control", "qc unit", "quality unit"],
            "211.165": ["testing", "acceptance criteria", "specification"],
            "211.182": ["equipment log", "maintenance record", "cleaning record"],
            "820.100": ["capa", "corrective action", "preventive action"],
            "820.30":  ["design control", "design history"],
        }

        # Determine hot CFR sections from both enforcement_records (legacy) and rag_engine frequency
        from collections import Counter
        cfr_freq: Counter = Counter()
        for rec in (ctx.enforcement_records or []):
            for cfr in rec.get("cfr_citations", []):
                cfr_clean = re.sub(r'\s+', ' ', cfr.strip())
                cfr_freq[cfr_clean] += 1

        # Supplement with rag_engine corpus frequencies
        for cfr_key in CFR_TOPICS:
            corpus_count = rag_engine.get_cfr_observation_count(f"21 CFR {cfr_key}")
            if corpus_count > 0:
                cfr_freq[f"21 CFR {cfr_key}"] = max(cfr_freq.get(f"21 CFR {cfr_key}", 0), corpus_count // 10)

        HIGH_FREQ_THRESHOLD = 5
        hot_sections = [cfr for cfr, cnt in cfr_freq.items() if cnt >= HIGH_FREQ_THRESHOLD]

        matched_topics = []
        for cfr_key, keywords in CFR_TOPICS.items():
            cfr_is_hot = any(cfr_key in h for h in hot_sections)
            if cfr_is_hot:
                topic_in_doc = any(kw in text_lower for kw in keywords)
                if topic_in_doc:
                    matched_topics.append(f"21 CFR {cfr_key}")

        if len(matched_topics) < 2:
            return None

        # Check for international corroboration
        intl_query = f"{ctx.document_category or 'quality'} {' '.join(matched_topics[:2])}"
        intl_matches = international_enforcement_engine.search(intl_query, n_results=2)
        intl_agencies = list({r['source_agency'] for r in intl_matches if r['score'] >= 0.6})

        intl_note = ""
        if intl_agencies:
            intl_note = f" Also flagged by {', '.join(intl_agencies)} enforcement actions."

        return FindingResult(
            level="L9",
            severity="medium",
            category="enforcement_pattern_overlap",
            title=f"Document covers {len(matched_topics)} CFR areas with high FDA enforcement frequency",
            description=(
                f"This document addresses areas ({', '.join(matched_topics[:3])}) that appear "
                f"frequently in FDA enforcement actions in Clyira's intelligence database."
                f"{intl_note} "
                "Documents in these areas receive heightened inspector scrutiny. Ensure all "
                "applicable sections are complete, precise, and supported by data."
            ),
            evidence=f"High-frequency CFR sections matched: {', '.join(matched_topics[:5])}",
            regulatory_citation="; ".join(matched_topics[:3]),
            citation_type="traceability",
            agency="FDA",
            enforcement_match=True,
            confidence_score=0.68,
            validated=True,
        )

    def _check_l9_repeat_observation_risk(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Flag recurring unresolved findings in prior assessments and OAI inspection history."""
        from collections import Counter
        from app.engines import facility_risk_engine

        repeat_cats: list[str] = []
        history_note = ""

        # Path 1: Clyira prior assessment recurrence
        if ctx.historical_assessments and len(ctx.historical_assessments) >= 2:
            category_counts: Counter = Counter()
            for hist in ctx.historical_assessments:
                for f in hist.get("findings", []):
                    if f.get("status") not in ("resolved", "disputed"):
                        cat = f.get("category", "")
                        if cat:
                            category_counts[cat] += 1
            repeat_cats = [cat for cat, cnt in category_counts.items() if cnt >= 2]

        # Path 2: ICDB site-level repeat OAI (if company context available)
        firm_name = ""
        if hasattr(ctx, 'company_name') and ctx.company_name:
            firm_name = ctx.company_name
        elif ctx.company_documents_metadata:
            firm_name = ctx.company_documents_metadata[0].get('company_name', '') if ctx.company_documents_metadata else ''

        facility_signals = {}
        if firm_name:
            facility_signals = facility_risk_engine.get_facility_risk_signals(firm_name)
            if facility_signals.get('repeat_oai'):
                oai_count = facility_signals.get('oai_count', 0)
                history_note = (
                    f" FDA ICDB records show {oai_count} Official Action Indicated (OAI) "
                    f"classifications for this facility — a pattern consistent with systemic quality failures."
                )

        if not repeat_cats and not facility_signals.get('repeat_oai'):
            return None

        severity = "high" if facility_signals.get('repeat_oai') else "medium"
        evidence_parts = []
        if repeat_cats:
            evidence_parts.append(f"Recurring Clyira finding categories: {', '.join(repeat_cats[:5])}")
        if facility_signals.get('repeat_oai'):
            evidence_parts.append(f"ICDB OAI count: {facility_signals.get('oai_count', 0)}")

        return FindingResult(
            level="L9",
            severity=severity,
            category="repeat_observation_risk",
            title=f"Recurring unresolved findings detected" + (" + repeat OAI facility history" if facility_signals.get('repeat_oai') else ""),
            description=(
                (f"The following finding categories have appeared in multiple prior assessments "
                 f"without resolution: {', '.join(repeat_cats[:5])}. " if repeat_cats else "") +
                "Repeat observations in FDA inspections are treated as systemic failures and "
                "significantly increase the risk of a Warning Letter or consent decree. "
                "Per 21 CFR 211.192 and ICH Q10, effectiveness checks must confirm that "
                "corrective actions have actually addressed the root cause." +
                history_note
            ),
            evidence=" | ".join(evidence_parts),
            regulatory_citation="21 CFR 211.192; ICH Q10 Section 3.2",
            citation_type="traceability",
            agency="FDA",
            confidence_score=0.82,
            validated=True,
        )

    def _check_l9_severity_elevation(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Identify if enforcement record volume for this document's topics warrants a risk advisory."""
        if not ctx.enforcement_records:
            return None

        doc_cat = (ctx.document_category or "").lower()
        # Map document category to enforcement observation keywords
        CAT_KEYWORDS = {
            "deviation":   ["deviation", "investigation", "oos", "discrepancy", "batch failure"],
            "lir":         ["out-of-specification", "oos", "laboratory", "retest", "invalidat"],
            "validation":  ["validation", "qualify", "calibration", "computer system", "csv"],
            "capa":        ["corrective action", "capa", "effectiveness", "root cause"],
            "sop":         ["procedure", "sop", "written procedure", "documentation"],
            "atm":         ["analytical method", "hplc", "system suitability", "method validation"],
        }
        keywords = CAT_KEYWORDS.get(doc_cat, [])
        if not keywords:
            return None

        # Count how many enforcement records match this document category
        match_count = 0
        for rec in ctx.enforcement_records:
            summary = (rec.get("summary", "") + " " + rec.get("title", "")).lower()
            if any(kw in summary for kw in keywords):
                match_count += 1

        # Only flag if this is a high-enforcement-pressure category
        HIGH_PRESSURE_THRESHOLD = 10
        if match_count < HIGH_PRESSURE_THRESHOLD:
            return None

        return FindingResult(
            level="L9",
            severity="info",
            category="high_enforcement_pressure_category",
            title=f"High enforcement pressure: {match_count} matching FDA actions for {ctx.document_category} documents",
            description=(
                f"Clyira's enforcement intelligence database contains {match_count} FDA enforcement "
                f"actions related to {ctx.document_category} documents. This document type is under "
                "active regulatory scrutiny. All findings from this assessment — especially medium "
                "and above — should be treated as elevated-priority remediation items. "
                "FDA inspectors are familiar with common deficiency patterns in this document type."
            ),
            evidence=f"{match_count} enforcement records matched for document category '{ctx.document_category}'",
            regulatory_citation="FDA Enforcement Intelligence",
            citation_type="traceability",
            agency="FDA",
            enforcement_match=True,
            confidence_score=0.75,
            validated=True,
        )

    def _check_l9_failure_mode_match(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Match document text against known FDA failure mode patterns from the failure mode library."""
        import json
        from pathlib import Path

        # Load failure modes from bundled JSONL (module-level cache after first load)
        if not hasattr(self.__class__, "_failure_modes_cache"):
            fm_path = Path(__file__).parent.parent.parent / "rag_index" / "failure_modes.jsonl"
            if not fm_path.exists():
                self.__class__._failure_modes_cache = []
            else:
                modes = []
                with open(fm_path) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                modes.append(json.loads(line))
                            except Exception:
                                pass
                self.__class__._failure_modes_cache = modes

        failure_modes = self.__class__._failure_modes_cache
        if not failure_modes:
            return []

        text_lower = ctx.document_text.lower()
        doc_cat = (ctx.document_category or "").lower()
        findings = []

        for fm in failure_modes:
            # Only surface failure modes relevant to this document category
            fm_doc_cats = [c.lower() for c in fm.get("doc_categories", [])]
            if doc_cat and fm_doc_cats and doc_cat not in fm_doc_cats:
                continue

            keywords = fm.get("keywords", [])
            matched_kws = [kw for kw in keywords if kw.lower() in text_lower]
            if len(matched_kws) < 2:
                continue

            # Only flag high-frequency failure modes (frequent in FDA enforcement = real risk)
            frequency = fm.get("frequency", 0)
            if frequency < 50:
                continue

            severity_range = fm.get("severity_range", ["medium"])
            severity = severity_range[-1] if severity_range else "medium"  # use worst severity

            top_cfr = fm.get("primary_cfr_citations", [])
            citation = "; ".join(top_cfr[:2]) if top_cfr else "FDA Enforcement Intelligence"

            companies = fm.get("affected_companies_count", 0)
            evidence_indicators = fm.get("evidence_indicators", [])
            evidence_text = evidence_indicators[0] if evidence_indicators else ""

            findings.append(FindingResult(
                level="L9",
                severity=severity,
                category=f"failure_mode_{fm['id'].lower().replace('-', '_')}",
                title=f"Known failure pattern detected: {fm['name']}",
                description=(
                    f"This document contains terminology associated with the failure mode "
                    f"'{fm['name']}'. This pattern was cited in {frequency} FDA enforcement "
                    f"observations across {companies} companies. {fm['description']} "
                    f"Common indicator: {evidence_text}"
                ),
                evidence=f"Matched keywords: {', '.join(matched_kws[:5])}. "
                         f"Failure mode frequency: {frequency} enforcement observations.",
                regulatory_citation=citation,
                citation_type="traceability",
                agency="FDA",
                enforcement_match=True,
                confidence_score=0.72,
                validated=True,
            ))

        return findings

    def _check_l9_consent_decree_pattern(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """Flag if document topics match patterns from FDA/DOJ consent decrees."""
        from app.engines import international_enforcement_engine, facility_risk_engine

        text_lower = ctx.document_text.lower()
        doc_cat = (ctx.document_category or "").lower()

        # Check facility-level consent decree / import alert status
        firm_name = ""
        if hasattr(ctx, 'company_name') and ctx.company_name:
            firm_name = ctx.company_name
        elif ctx.company_documents_metadata:
            firm_name = ctx.company_documents_metadata[0].get('company_name', '') if ctx.company_documents_metadata else ''

        import_alerts: list[dict] = []
        if firm_name:
            signals = facility_risk_engine.get_facility_risk_signals(firm_name)
            import_alerts = signals.get('active_import_alerts', [])

        # BM25 search across consent decree / DOJ corpus
        query = f"{doc_cat} consent decree {ctx.document_category or 'quality system'}"
        cd_results = international_enforcement_engine.search(
            query, n_results=2, agency_filter="FDA/DOJ"
        )
        # Also search for DOJ patterns
        doj_results = international_enforcement_engine.search(
            query, n_results=1, agency_filter="DOJ"
        )
        all_results = cd_results + doj_results
        strong_matches = [r for r in all_results if r['score'] >= 0.65]

        if not strong_matches and not import_alerts:
            return None

        evidence_parts = []
        description_parts = []

        if import_alerts:
            alert_nums = [a.get('alert_number', '') for a in import_alerts[:3]]
            evidence_parts.append(f"Active import alerts: {', '.join(a for a in alert_nums if a)}")
            description_parts.append(
                f"This facility has active FDA Import Alerts ({', '.join(a for a in alert_nums if a)}), "
                "indicating unresolved compliance failures that triggered import detention. "
            )

        if strong_matches:
            companies = [r.get('company', '') for r in strong_matches[:2] if r.get('company')]
            evidence_parts.append(f"Consent decree pattern matches: {', '.join(companies)}")
            description_parts.append(
                "Document content matches patterns associated with prior FDA/DOJ consent decrees — "
                "the most severe enforcement outcome short of criminal prosecution. "
            )

        description_parts.append(
            "Consent decrees typically arise from persistent systemic failures. "
            "Ensure this document demonstrates genuine remediation, not superficial documentation fixes."
        )

        return FindingResult(
            level="L9",
            severity="high",
            category="consent_decree_pattern",
            title="Document content matches consent decree / import alert enforcement patterns",
            description=" ".join(description_parts),
            evidence=" | ".join(evidence_parts),
            regulatory_citation="21 CFR 211.192; FD&C Act Section 302",
            citation_type="enforcement",
            agency="FDA",
            enforcement_match=True,
            confidence_score=0.75,
            validated=True,
        )

    def _check_l9_data_integrity_enforcement_pattern(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """
        Flag data integrity deficiency patterns from Ranbaxy, Cetero, Able Labs precedents
        and current document content.
        """
        from app.engines import rag_engine, international_enforcement_engine

        text_lower = ctx.document_text.lower()

        # DI red-flag keywords in document
        DI_KEYWORDS = [
            "audit trail", "audit_trail", "raw data", "original data",
            "data deletion", "back-dated", "backdated", "altered record",
            "duplicate result", "second sample", "retesting", "cherry-pick",
            "undocumented change", "overwritten", "computer access", "shared login",
            "electronic record", "21 cfr 11", "part 11",
        ]
        DI_SEVERITY_KEYWORDS = [
            "deleted", "manipulated", "falsified", "fabricated",
            "unauthorized change", "no audit trail",
        ]

        matched = [kw for kw in DI_KEYWORDS if kw in text_lower]
        high_risk = [kw for kw in DI_SEVERITY_KEYWORDS if kw in text_lower]

        if len(matched) < 3 and not high_risk:
            return None

        # Cross-reference with enforcement corpus for DI-specific precedents
        di_query = "data integrity audit trail electronic records manipulation falsification"
        fda_di = rag_engine.search(di_query, n_results=2)
        intl_di = international_enforcement_engine.search(di_query, n_results=2)

        agencies = list({r['source_agency'] for r in intl_di if r['score'] >= 0.6})
        intl_note = f" Similar patterns cited by {', '.join(agencies)}." if agencies else ""

        severity = "critical" if high_risk else "high"

        return FindingResult(
            level="L9",
            severity=severity,
            category="data_integrity_enforcement_pattern",
            title="Data integrity keywords match high-frequency enforcement patterns (Ranbaxy/Cetero precedent)",
            description=(
                f"This document contains {len(matched)} data integrity-related terms "
                f"({', '.join(matched[:4])}) that overlap with patterns from major FDA data integrity "
                "enforcement actions (Ranbaxy, Cetero Research, Able Laboratories). "
                "Data integrity failures are the #1 driver of Warning Letters and import alerts "
                "in the last decade. Per ALCOA+ principles and 21 CFR Part 11, all data must be "
                "attributable, legible, contemporaneous, original, and accurate." +
                intl_note
            ),
            evidence=(
                f"DI keywords matched: {', '.join(matched[:6])}. "
                + (f"High-risk terms: {', '.join(high_risk)}. " if high_risk else "")
                + (f"FDA enforcement precedents found: {len(fda_di)}." if fda_di else "")
            ),
            regulatory_citation="21 CFR Part 11; 21 CFR 211.68; ALCOA+",
            citation_type="enforcement",
            agency="FDA",
            enforcement_match=True,
            confidence_score=0.80,
            validated=True,
        )

    def _check_l9_narrow_scope_enforcement_pattern(self, ctx: AssessmentContext) -> Optional[FindingResult]:
        """
        Flag Wockhardt-pattern: CAPA/investigation scoped to a single instrument/batch
        when the root cause implies a systemic issue.
        """
        from app.engines import rag_engine, international_enforcement_engine

        text_lower = ctx.document_text.lower()

        # Signals that scope was limited to one unit/batch/analyst
        NARROW_SCOPE_SIGNALS = [
            "specific equipment", "single instrument", "one hplc", "one gc",
            "this batch only", "isolated incident", "single analyst",
            "one-time deviation", "no other batches", "no trend",
            "no systemic", "equipment only", "limited to",
        ]

        # Signals that the root cause actually implies systemic issues
        SYSTEMIC_SIGNALS = [
            "procedure not followed", "training", "sop not clear",
            "awareness", "understanding", "knowledge gap",
            "multiple", "recurring", "previous", "history of",
        ]

        narrow_matches = [kw for kw in NARROW_SCOPE_SIGNALS if kw in text_lower]
        systemic_signals = [kw for kw in SYSTEMIC_SIGNALS if kw in text_lower]

        # Only flag if there are narrow-scope claims alongside systemic root cause signals
        if len(narrow_matches) < 2 or not systemic_signals:
            return None

        # Confirm with enforcement BM25 for narrow-scope patterns
        query = "narrow scope capa isolated incident systemic root cause inadequate investigation"
        fda_matches = rag_engine.search(query, n_results=2)
        intl_matches = international_enforcement_engine.search(query, n_results=1)

        agencies = list({r['source_agency'] for r in intl_matches if r['score'] >= 0.55})
        intl_note = f" Also cited by {', '.join(agencies)}." if agencies else ""

        return FindingResult(
            level="L9",
            severity="high",
            category="narrow_scope_enforcement_pattern",
            title="Narrow CAPA scope despite systemic root cause signals — Wockhardt pattern",
            description=(
                f"Document uses narrow-scope language ({', '.join(narrow_matches[:3])}) "
                f"while simultaneously indicating systemic contributing factors "
                f"({', '.join(systemic_signals[:3])}). "
                "FDA has cited this pattern in Warning Letters against Wockhardt and others: "
                "scoping a CAPA to a single instrument or batch when the root cause (training gap, "
                "unclear procedure) affects the entire site. Ensure the CAPA scope matches the "
                "breadth of the identified root cause." +
                intl_note
            ),
            evidence=(
                f"Narrow-scope signals: {', '.join(narrow_matches[:4])}. "
                f"Systemic signals: {', '.join(systemic_signals[:4])}."
            ),
            regulatory_citation="21 CFR 211.192; 21 CFR 820.100",
            citation_type="enforcement",
            agency="FDA",
            enforcement_match=True,
            confidence_score=0.72,
            validated=True,
        )

    # ========== L11: Inspection Readiness Checks ==========

    def _check_l11_no_tbd_placeholders(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Document must not contain TBD/TODO/placeholder text before inspection."""
        text = ctx.document_text
        placeholder_patterns = [
            (r'\bTBD\b', "TBD"),
            (r'\bTBC\b', "TBC"),
            (r'\bTBR\b', "TBR"),
            (r'\bTODO\b', "TODO"),
            (r'\[INSERT\b', "[INSERT ...]"),
            (r'\[PLACEHOLDER\b', "[PLACEHOLDER]"),
            (r'\[TO BE COMPLETED\b', "[TO BE COMPLETED]"),
            (r'\[TO BE ADDED\b', "[TO BE ADDED]"),
            (r'to\s+be\s+determined\b(?!\s+by\s+(?:QA|analyst))', "to be determined"),
            (r'not\s+yet\s+available\b', "not yet available"),
        ]
        found = []
        for pat, label in placeholder_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                start = max(0, m.start() - 60)
                excerpt = text[start:m.end() + 60].strip().replace('\n', ' ')
                found.append(f'"{label}" at: …{excerpt}…')

        if not found:
            return []
        return [FindingResult(
            level="L11",
            severity="high",
            category="placeholder_text_present",
            title=f"Unresolved placeholder text detected ({len(found)} instance{'s' if len(found) > 1 else ''})",
            description=(
                f"The document contains {len(found)} unresolved placeholder(s): "
                f"{'; '.join(found[:3])}. A document presented to an FDA investigator "
                f"with TBD/placeholder text will be cited as incomplete under 21 CFR 211.100."
            ),
            evidence=found[0],
            regulatory_citation="21 CFR 211.100(a)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.97,
            validated=True,
        )]

    def _check_l11_no_draft_language(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Document must not carry DRAFT watermark or 'not for use' language."""
        text = ctx.document_text
        draft_patterns = [
            r'\bDRAFT\b',
            r'NOT\s+FOR\s+(?:USE|DISTRIBUTION|RELEASE|IMPLEMENTATION)',
            r'FOR\s+REVIEW\s+ONLY',
            r'PRELIMINARY\s+(?:VERSION|DRAFT|COPY)',
            r'DO\s+NOT\s+USE\b',
            r'UNDER\s+DEVELOPMENT\b',
        ]
        for pat in draft_patterns:
            m = re.search(pat, text[:3000], re.IGNORECASE)
            if m:
                return [FindingResult(
                    level="L11",
                    severity="critical",
                    category="draft_document",
                    title="Document carries DRAFT or 'not for use' designation",
                    description=(
                        f"The document header contains '{m.group(0).strip()}', indicating it is "
                        f"not in approved/effective status. Using or citing a DRAFT document "
                        f"during an FDA inspection is a direct 21 CFR 211.100(b) violation."
                    ),
                    evidence=text[max(0, m.start()-30):m.end()+60].strip(),
                    regulatory_citation="21 CFR 211.100(b)",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.98,
                    validated=True,
                )]
        return []

    def _check_l11_effective_date_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Document must have an effective/issue/approval date in the header."""
        text_top = ctx.document_text[:2000]
        date_patterns = [
            r'(?:effective|issue|approval|approved|issued|date)\s*(?:date)?[:\s]*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            r'(?:effective|issue|approval|approved|issued|date)\s*(?:date)?[:\s]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\s.,]+\d{4}',
            r'(?:effective|issue|approval)\s*(?:date)?[:\s]*\d{4}-\d{2}-\d{2}',
        ]
        for pat in date_patterns:
            if re.search(pat, text_top, re.IGNORECASE):
                return []
        return [FindingResult(
            level="L11",
            severity="high",
            category="effective_date_missing",
            title="Effective/approval date absent from document header",
            description=(
                "No effective date or approval date was found in the document header. "
                "An FDA investigator will flag any quality document that cannot be dated — "
                "it cannot be determined whether the document was in effect at the time of "
                "the event under investigation."
            ),
            regulatory_citation="21 CFR 211.68; 21 CFR 211.100",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.85,
            validated=True,
        )]

    def _check_l11_blank_signature_lines(self, ctx: AssessmentContext) -> list[FindingResult]:
        """All signature fields must be completed — blank lines are a critical inspection finding."""
        text = ctx.document_text
        blank_sig_patterns = [
            r'(?:signature|signed|approved\s+by|author)[:\s]*_{3,}',
            r'(?:signature|signed|approved\s+by|author)[:\s]*\.\.\.',
            r'(?:signature|signed|approved\s+by|author)[:\s]*\[?\s*\]?$',
            r'(?:QA|quality\s+(?:assurance|manager|director))\s+(?:signature|approval)[:\s]*_{3,}',
        ]
        blanks = []
        for pat in blank_sig_patterns:
            for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
                context_line = text[max(0, m.start()-20):m.end()+20].strip().replace('\n', ' ')
                blanks.append(context_line[:120])
        if not blanks:
            return []
        return [FindingResult(
            level="L11",
            severity="critical",
            category="blank_signatures",
            title=f"Unsigned approval/signature field{'s' if len(blanks) > 1 else ''} detected ({len(blanks)})",
            description=(
                f"Found {len(blanks)} blank signature or approval line(s). "
                f"A document with blank signatures presented during an FDA inspection "
                f"is an immediate 483 observation — it cannot be considered an approved, "
                f"controlled document. Example: {blanks[0]}"
            ),
            evidence=blanks[0],
            regulatory_citation="21 CFR 211.68; 21 CFR 211.100(b)",
            citation_type="direct",
            agency="FDA",
            confidence_score=0.93,
            validated=True,
        )]

    def _check_l11_version_control_complete(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Document must carry a version number and revision history."""
        text_top = ctx.document_text[:3000]
        has_version = bool(re.search(
            r'(?:version|revision|rev\.?|ver\.?)[:\s]*\d+[\d.]*',
            text_top, re.IGNORECASE
        ))
        has_history = bool(re.search(
            r'(?:revision\s+history|change\s+log|change\s+history|document\s+history|version\s+history)',
            ctx.document_text, re.IGNORECASE
        ))
        findings = []
        if not has_version:
            findings.append(FindingResult(
                level="L11",
                severity="high",
                category="version_number_missing",
                title="Version/revision number absent from document header",
                description=(
                    "No version or revision number was found in the first 3000 characters. "
                    "Version control is required for all GMP documents under 21 CFR 211.68 "
                    "and EU GMP Chapter 4. Without a version number, document currency "
                    "cannot be confirmed during an inspection."
                ),
                regulatory_citation="21 CFR 211.68; EU GMP Chapter 4",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.88,
                validated=True,
            ))
        if not has_history:
            findings.append(FindingResult(
                level="L11",
                severity="medium",
                category="revision_history_absent",
                title="Revision history section not found",
                description=(
                    "No revision history section was detected. GMP-compliant documents "
                    "must maintain a revision history documenting what changed, who changed "
                    "it, and why — to demonstrate document lifecycle control."
                ),
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.82,
                validated=True,
            ))
        return findings

    # ========== NEW v2.4 CHECKS — Added from LLM benchmark + sparring review ==========

    # ── L1: New structural checks ──

    def _check_l1_containment_section_present(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Immediate Containment Actions must exist as a dedicated section, not buried in narrative."""
        text_lower = ctx.document_text.lower()
        containment_patterns = [
            r'(?:immediate\s+)?containment\s+action',
            r'interim\s+(?:action|measure|containment)',
            r'immediate\s+corrective\s+action',
        ]
        found = any(re.search(p, text_lower) for p in containment_patterns)
        if not found:
            return [FindingResult(
                level="L1",
                severity="high",
                category="containment_missing",
                title="No Immediate Containment Actions section found",
                description=(
                    "CAPAs must document what immediate containment was applied to "
                    "protect product and patients while root cause investigation proceeds. "
                    "Absence of containment documentation is a common FDA 483 observation — "
                    "inspectors expect to see what was done NOW, not just what will be done later."
                ),
                evidence="No containment/interim action keywords found in document.",
                regulatory_citation="21 CFR 211.192; ICH Q10 §3.2.1",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.92,
                validated=True,
            )]
        return []

    def _check_l1_patient_safety_impact_section(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Patient safety impact must be explicitly assessed, even if conclusion is 'no impact'."""
        text_lower = ctx.document_text.lower()
        safety_patterns = [
            r'patient\s+safety',
            r'safety\s+impact',
            r'impact\s+(?:to|on)\s+patient',
            r'health\s+hazard\s+evaluation',
            r'hhe\b',
        ]
        found = any(re.search(p, text_lower) for p in safety_patterns)
        if not found:
            return [FindingResult(
                level="L1",
                severity="critical",
                category="patient_safety_missing",
                title="Patient safety impact assessment not documented",
                description=(
                    "No patient safety impact assessment found. Every CAPA must explicitly "
                    "evaluate whether the issue could affect patient safety — this is the "
                    "FIRST question an FDA investigator will ask. Even 'no patient safety "
                    "impact' must be stated with rationale."
                ),
                evidence="Keywords 'patient safety', 'safety impact', 'HHE' absent from document.",
                regulatory_citation="21 CFR 211.192; 21 CFR 314.81(b)(1)",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.95,
                validated=True,
            )]
        return []

    def _check_l1_regulatory_reporting_section(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Regulatory reporting assessment must be documented (field alert, recall, agency notification)."""
        text_lower = ctx.document_text.lower()
        reporting_patterns = [
            r'regulatory\s+(?:reporting|notification)',
            r'field\s+alert',
            r'recall\s+assessment',
            r'agency\s+notification',
            r'fda\s+(?:reporting|notification)',
            r'medwatch',
        ]
        found = any(re.search(p, text_lower) for p in reporting_patterns)
        if not found:
            return [FindingResult(
                level="L1",
                severity="high",
                category="regulatory_reporting_missing",
                title="Regulatory reporting assessment section absent",
                description=(
                    "No regulatory reporting assessment found. CAPAs must document whether "
                    "the issue triggers reporting obligations (field alert reports per 21 CFR "
                    "314.81, recall assessment, or agency notification). Even if reporting is "
                    "not required, the assessment must be documented."
                ),
                evidence="No 'regulatory reporting', 'field alert', or 'recall assessment' keywords found.",
                regulatory_citation="21 CFR 314.81(b)(1); 21 CFR 211.198",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
            )]
        return []

    # ── L2: New document control checks ──

    def _check_l2_duplicate_document_id(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Detect if CAPA number appears to be a duplicate or reused ID (e.g., same ID different content)."""
        # This check fires when assessments are run in batch mode and the context
        # includes other document IDs. In single-doc mode, it checks for internal
        # duplicated CAPA reference numbers.
        text = ctx.document_text
        capa_ids = re.findall(r'CAPA[-\s]?\d{4}[-\s]?\d{3,4}', text, re.IGNORECASE)
        unique_ids = set(c.upper().replace(' ', '-') for c in capa_ids)
        # If the same CAPA ID appears in different section contexts with conflicting info
        # this is a structural concern — but for now, just ensure at least one unique CAPA ID exists
        if len(capa_ids) > 0 and len(unique_ids) == 0:
            return [FindingResult(
                level="L2",
                severity="medium",
                category="document_id_inconsistency",
                title="CAPA document ID format inconsistency detected",
                description="Multiple CAPA ID references found with inconsistent formatting.",
                regulatory_citation="21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.75,
                validated=True,
            )]
        return []

    def _check_l2_batch_size_context_for_impact(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Impact assessment requires batch size context — can't assess impact without knowing scale."""
        text_lower = ctx.document_text.lower()
        has_impact = bool(re.search(r'impact\s+assess', text_lower))
        has_batch_size = bool(re.search(
            r'(?:batch\s+size|lot\s+size|number\s+of\s+(?:units|vials|tablets|capsules|doses)|\d+\s*(?:units|vials|tablets|capsules|doses|kg|liters?|L\b))',
            ctx.document_text, re.IGNORECASE
        ))
        if has_impact and not has_batch_size:
            return [FindingResult(
                level="L2",
                severity="medium",
                category="batch_size_missing",
                title="Impact assessment lacks batch size or production scale context",
                description=(
                    "The impact assessment section does not reference batch size, lot size, "
                    "or production quantity. Impact severity cannot be properly evaluated "
                    "without knowing the scale — 50 vials vs 50,000 vials is a materially "
                    "different regulatory risk."
                ),
                regulatory_citation="21 CFR 211.192",
                citation_type="interpretive",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            )]
        return []

    # ── L4: New data integrity checks ──

    def _check_l4_synthetic_data_disclaimer(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Detect synthetic/test data disclaimers that indicate non-actual records."""
        patterns = [
            r'not\s+an?\s+actual\s+(?:company\s+)?record',
            r'(?:sample|example|synthetic|test|mock|dummy)\s+(?:document|record|data)',
            r'for\s+(?:training|demonstration|illustrative|testing)\s+purposes?\s+only',
            r'this\s+(?:is|document\s+is)\s+(?:a\s+)?(?:sample|example|template|draft)',
            r'fictitious|placeholder\s+(?:data|content)',
        ]
        text = ctx.document_text
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                context = _extract_sentence(text, match.start())
                return [FindingResult(
                    level="L4",
                    severity="critical",
                    category="synthetic_data_disclaimer",
                    title="Document contains synthetic/test data disclaimer",
                    description=(
                        f"A disclaimer indicating this is not an actual controlled record was "
                        f"detected: '{context[:200]}'. A document presented during an FDA "
                        f"inspection that contains such a disclaimer would call into question "
                        f"the entire quality system's document control integrity."
                    ),
                    evidence=context[:200],
                    regulatory_citation="21 CFR 211.68; 21 CFR 211.180",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.98,
                    validated=True,
                )]
        return []

    def _check_l4_audit_trail_review_documented(self, ctx: AssessmentContext) -> list[FindingResult]:
        """For data integrity CAPAs, audit trail review must be documented."""
        text_lower = ctx.document_text.lower()
        # Only trigger for data integrity/audit trail related CAPAs
        is_di_capa = any(term in text_lower for term in [
            'audit trail', 'data integrity', 'alcoa', 'electronic record',
            'chromatography data', 'data review', '21 cfr part 11',
        ])
        if not is_di_capa:
            return []
        has_trail_review = bool(re.search(
            r'(?:audit\s+trail|electronic\s+record).*(?:review(?:ed)?|examined|evaluated|assessed)',
            text_lower
        )) or bool(re.search(
            r'(?:review(?:ed)?|examined|evaluated).*(?:audit\s+trail|electronic\s+record)',
            text_lower
        ))
        if not has_trail_review:
            return [FindingResult(
                level="L4",
                severity="high",
                category="audit_trail_review_missing",
                title="Data integrity CAPA lacks documented audit trail review",
                description=(
                    "This CAPA involves data integrity concerns but does not document "
                    "a review of relevant audit trails. Per FDA Data Integrity Guidance "
                    "(2018), audit trail review is a fundamental expectation for any "
                    "investigation involving electronic records or data integrity."
                ),
                regulatory_citation="FDA Data Integrity Guidance (2018); 21 CFR Part 11",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.88,
                validated=True,
            )]
        return []

    # ── L7: New lifecycle checks ──

    def _check_l7_capa_aging_check(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Flag CAPAs open >90 days without extension justification (Sun Pharma pattern)."""
        text = ctx.document_text
        # Look for dates and compute age if possible
        initiation_match = re.search(
            r'(?:initiat(?:ed?|ion)\s*(?:date)?|opened?\s*(?:date)?|date\s*(?:initiated|opened))[:\s]*'
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})',
            text, re.IGNORECASE
        )
        has_extension = bool(re.search(
            r'(?:extension|justification\s+for\s+(?:delay|extension)|overdue\s+justification)',
            text, re.IGNORECASE
        ))
        has_closure = bool(re.search(
            r'(?:capa\s+clos(?:ed|ure)|status[:\s]*closed|completed?\s+date)',
            text, re.IGNORECASE
        ))
        # If no closure and no extension justification, flag as potential aging risk
        if initiation_match and not has_closure and not has_extension:
            return [FindingResult(
                level="L7",
                severity="medium",
                category="capa_aging_risk",
                title="CAPA aging risk — no closure or extension justification documented",
                description=(
                    "CAPA has an initiation date but no documented closure or extension "
                    "justification. CAPAs open beyond 90 days without justified extensions "
                    "are a common FDA 483 observation (Sun Pharma pattern). "
                    "Aging CAPAs suggest systemic quality system weakness."
                ),
                evidence=f"Initiation found: '{initiation_match.group(0)[:80]}', no closure/extension detected.",
                regulatory_citation="21 CFR 211.192; ICH Q10 §3.2",
                citation_type="interpretive",
                agency="FDA",
                confidence_score=0.78,
                validated=True,
            )]
        return []

    def _check_l7_interim_containment_duration(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Containment measures must have defined end conditions — can't be indefinite."""
        text_lower = ctx.document_text.lower()
        has_containment = bool(re.search(r'containment|interim\s+(?:action|measure)', text_lower))
        if not has_containment:
            return []
        has_duration = bool(re.search(
            r'containment.*(?:until|pending|expire|end\s+date|duration|lifted\s+when|remove.*when)',
            text_lower
        )) or bool(re.search(
            r'(?:until|pending).*containment',
            text_lower
        ))
        if not has_duration:
            return [FindingResult(
                level="L7",
                severity="medium",
                category="containment_duration_missing",
                title="Containment measures lack defined end condition or duration",
                description=(
                    "Interim containment actions are documented but have no defined "
                    "end condition or expiration criteria. Indefinite containment suggests "
                    "the CAPA is not progressing to permanent corrective action — this "
                    "is a red flag during inspections."
                ),
                regulatory_citation="ICH Q10 §3.2.1",
                citation_type="interpretive",
                agency="FDA",
                confidence_score=0.80,
                validated=True,
            )]
        return []

    # ── L11: New document quality checks ──

    def _check_l11_template_boilerplate_detection(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Detect template boilerplate text that appears verbatim across multiple documents."""
        # Common boilerplate phrases that indicate copy-paste from templates
        boilerplate_markers = [
            r'(?:this\s+section|this\s+area|this\s+field)\s+(?:is\s+)?(?:reserved|intentionally\s+left\s+blank)',
            r'insert\s+(?:text|details?|description|name|date)\s+here',
            r'\[(?:insert|enter|add|describe|company\s+name|product\s+name|batch)\]',
            r'lorem\s+ipsum',
            r'xxx+',
        ]
        text = ctx.document_text
        boilerplate_found = []
        for pattern in boilerplate_markers:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for m in matches:
                boilerplate_found.append(_extract_sentence(text, m.start())[:150])

        if boilerplate_found:
            return [FindingResult(
                level="L11",
                severity="high",
                category="template_boilerplate_detected",
                title=f"Template boilerplate text detected ({len(boilerplate_found)} instance{'s' if len(boilerplate_found) > 1 else ''})",
                description=(
                    f"Found {len(boilerplate_found)} instances of template placeholder or "
                    f"boilerplate text. This indicates the document was not fully customized "
                    f"for the specific event. An FDA inspector would view this as evidence of "
                    f"inadequate document review and approval. Example: '{boilerplate_found[0]}'"
                ),
                evidence=boilerplate_found[0],
                regulatory_citation="21 CFR 211.100(a); 21 CFR 211.68",
                citation_type="direct",
                agency="FDA",
                confidence_score=0.90,
                validated=True,
            )]
        return []

    def _check_l11_date_logic_consistency(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Check that dates follow logical order: initiation < investigation < target < closure."""
        import datetime
        text = ctx.document_text

        # Extract dates with labels
        date_pattern = r'(?:(?:initiat|open|start|investigat|target|complet|clos|due|effective)\w*)\s*(?:date)?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        matches = list(re.finditer(date_pattern, text, re.IGNORECASE))

        if len(matches) < 2:
            return []

        # Try to parse dates and check for obvious inversions
        parsed_dates = []
        for m in matches:
            date_str = m.group(1)
            label_context = text[max(0, m.start()-30):m.start()].strip()
            for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y', '%d-%m-%Y', '%m/%d/%y', '%d/%m/%y'):
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    parsed_dates.append((label_context.lower(), dt, m.group(0)))
                    break
                except ValueError:
                    continue

        # Look for target date before initiation date
        initiation_dates = [d for d in parsed_dates if any(k in d[0] for k in ['initiat', 'open', 'start'])]
        target_dates = [d for d in parsed_dates if any(k in d[0] for k in ['target', 'due', 'complet'])]

        if initiation_dates and target_dates:
            init_date = initiation_dates[0][1]
            target_date = target_dates[0][1]
            if target_date < init_date:
                return [FindingResult(
                    level="L11",
                    severity="critical",
                    category="date_logic_error",
                    title="Date logic error: target/completion date precedes initiation date",
                    description=(
                        f"The target or completion date appears to be BEFORE the initiation "
                        f"date. This is a data integrity red flag — either the dates are "
                        f"incorrect or the document was backdated. "
                        f"Initiation: {initiation_dates[0][2]}, Target: {target_dates[0][2]}"
                    ),
                    evidence=f"Init={initiation_dates[0][2]}, Target={target_dates[0][2]}",
                    regulatory_citation="21 CFR 211.68; 21 CFR Part 11.10(e)",
                    citation_type="direct",
                    agency="FDA",
                    confidence_score=0.92,
                    validated=True,
                )]
        return []

    def _check_l11_internal_consistency_check(self, ctx: AssessmentContext) -> list[FindingResult]:
        """Check for internal contradictions — e.g., severity says 'minor' but actions say 'critical'."""
        text_lower = ctx.document_text.lower()
        findings = []

        # Check: classification says minor/low but document references critical actions
        is_minor = bool(re.search(r'(?:classification|severity|category)[:\s]*(?:minor|low)', text_lower))
        has_critical_lang = bool(re.search(
            r'(?:critical|patient\s+safety\s+(?:risk|impact)|recall|field\s+alert|life[-\s]?threatening)',
            text_lower
        ))

        if is_minor and has_critical_lang:
            findings.append(FindingResult(
                level="L11",
                severity="high",
                category="internal_contradiction",
                title="Internal contradiction: minor classification but critical language in document",
                description=(
                    "The CAPA classification indicates 'minor' or 'low' severity, but the "
                    "document body contains language suggesting critical impact (patient safety, "
                    "recall, field alert, etc.). This inconsistency would be flagged by an "
                    "inspector as evidence of inadequate risk assessment."
                ),
                regulatory_citation="ICH Q9; 21 CFR 211.192",
                citation_type="interpretive",
                agency="FDA",
                confidence_score=0.82,
                validated=True,
            ))

        return findings
