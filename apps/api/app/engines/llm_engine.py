"""
LLM Engine — Gemini-powered semantic analysis.
Handles: L3 (Content Quality), L6 (Cross-Doc Consistency), L8 (Regulatory Gap),
         L10 (Longitudinal Intelligence), and remediation generation.
"""
import json
import logging

from google import genai
from google.genai import types as genai_types

from app.core.config import settings
from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)


class LLMEngine:
    """
    Semantic analysis engine powered by Gemini.
    Uses structured prompts with DTAP context for precise assessment.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        self.max_tokens = settings.GEMINI_MAX_TOKENS

    async def run_checks(self, level: str, checks: list[str], context: AssessmentContext) -> list[FindingResult]:
        """Evaluate specific named checks via LLM (fallback for unimplemented rule checks)."""
        if not settings.GEMINI_API_KEY:
            return []
        profile = context.dtap_profile
        check_labels = [c.replace("_", " ").title() for c in checks]

        prompt = (
            f"## Document Assessment — Level {level} Checks\n"
            f"Document type: {profile.document_category} (DTAP: {profile.dtap_id})\n\n"
            f"### Checks to perform:\n"
            + "\n".join(f"- {label}" for label in check_labels)
            + f"\n\n### Document Content:\n{context.document_text[:40000]}\n\n"
            f"### Regulatory context: agencies = {', '.join(context.company_agencies)}\n\n"
            f"### Output Instructions:\n"
            f"For each check above, identify ALL gaps and non-conformances. "
            f"Be comprehensive — flag anything missing, ambiguous, or non-compliant. "
            f"Return ONLY a JSON array of findings.\n"
        )
        if context.regulatory_frameworks:
            prompt += f"Frameworks to assess against: {', '.join(context.regulatory_frameworks)}\n"

        system = self._get_system_prompt(level)
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.3,
                    max_output_tokens=self.max_tokens,
                ),
            )
            return self._parse_findings_response(response.text, level)
        except Exception as e:
            logger.error(f"LLM run_checks failed for {level}: {e}")
            return []

    async def run(self, context: AssessmentContext, levels: list[str]) -> list[FindingResult]:
        """Run LLM assessment for specified levels"""
        findings: list[FindingResult] = []

        for level in levels:
            level_config = context.dtap_profile.levels.get(level)
            if not level_config or not level_config.enabled:
                continue
            if level_config.engine not in ("llm", "hybrid"):
                continue

            level_findings = await self._assess_level(level, context)
            findings.extend(level_findings)

        return findings

    async def _assess_level(self, level: str, context: AssessmentContext) -> list[FindingResult]:
        """Run LLM assessment for a single level"""
        if not settings.GEMINI_API_KEY:
            logger.warning(f"Skipping LLM assessment for {level} — no Gemini API key configured")
            return []

        system_prompt = self._get_system_prompt(level)
        user_prompt = self._build_assessment_prompt(level, context)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                    max_output_tokens=self.max_tokens,
                ),
            )
            findings = self._parse_findings_response(response.text, level)
            return findings

        except Exception as e:
            logger.error(f"LLM assessment failed for {level}: {e}")
            return []

    def _get_system_prompt(self, level: str) -> str:
        return f"""You are a senior FDA/EMA regulatory assessor and GMP compliance expert with 20+ years of experience conducting inspections. You are performing a Level {level} assessment of a pharmaceutical quality document.

YOUR MANDATE: Be THOROUGH and COMPREHENSIVE. Find ALL issues — gaps, ambiguities, missing elements, weak language, incomplete procedures, data integrity risks, and regulatory non-conformances. An undetected finding that becomes an FDA 483 observation is worse than a false positive that gets reviewed and closed.

ASSESSMENT APPROACH:
- Think like an FDA investigator who will issue a 483 observation for every gap
- Flag anything that is unclear, incomplete, missing, ambiguous, or non-compliant
- Include both major findings (critical/high) AND minor observations (medium/low/info)
- Do not self-censor — surface every potential issue you identify
- A document that passes your review should be genuinely inspection-ready

SEVERITY GUIDE:
- critical: Would result in a Warning Letter or import alert
- high: Would result in a 483 observation or CAPA requirement
- medium: Would be flagged in an internal audit
- low: Best practice gap or minor documentation weakness
- info: Advisory observation for improvement

CITATION TYPES:
- "direct": Explicit regulatory requirement (cite specific CFR/Annex/Guidance section)
- "traceability": Internal consistency or cross-reference requirement
- "substantive": Industry best practice with regulatory backing

OUTPUT FORMAT: Return a JSON array of ALL findings. Do not omit findings to save space.
Each finding: {{"level": "...", "severity": "...", "category": "...", "title": "...",
"description": "...", "evidence": "...", "location": "...",
"regulatory_citation": "...", "citation_type": "...", "agency": "...",
"suggestion_draft": "...", "confidence_score": 0.0}}"""

    def _build_assessment_prompt(self, level: str, context: AssessmentContext) -> str:
        """Build the assessment prompt with full context"""
        profile = context.dtap_profile
        level_config = profile.levels[level]

        prompt_parts = [
            f"## Document Under Assessment",
            f"Category: {profile.document_category} (DTAP: {profile.dtap_id})",
            f"Assessment Level: {level} ({self._get_level_name(level)})",
            f"",
            f"### Checks to Perform:",
        ]

        for check in level_config.checks:
            prompt_parts.append(f"- {check.replace('_', ' ').title()}")

        prompt_parts.append(f"\n### Document Content (truncated to key sections):")
        doc_excerpt = context.document_text[:50000]
        prompt_parts.append(doc_excerpt)

        if context.regulatory_context and level in ("L8",):
            prompt_parts.append("\n### Relevant Regulatory Requirements:")
            for reg in context.regulatory_context[:10]:
                prompt_parts.append(f"- [{reg.get('citation_reference', '')}] {reg.get('content', '')[:200]}")

        if context.user_references:
            prompt_parts.append("\n### Organization-Specific References (uploaded by user):")
            for ref in context.user_references[:5]:
                prompt_parts.append(f"- {ref.get('title', 'Reference')}: {ref.get('extracted_text', '')[:500]}")

        if context.company_agencies:
            prompt_parts.append(f"\n### Applicable Agencies: {', '.join(context.company_agencies)}")

        if context.regulatory_frameworks:
            prompt_parts.append(f"\n### Regulatory Frameworks Selected for Assessment:")
            prompt_parts.append(f"Assess this document specifically against: {', '.join(context.regulatory_frameworks)}")
            prompt_parts.append("Prioritize citations and gap analysis from these frameworks only.")

        prompt_parts.append("""
### Output Instructions:
Return a comprehensive JSON array of ALL findings for every check listed above.
For each check, look deeply — report every gap, ambiguity, missing element, weak language, or non-conformance.
If a section is present but incomplete, flag it. If language is vague, flag it. If a requirement is implied but not explicit, flag it.
Aim for complete coverage: it is better to report 20 findings and have 2 dismissed than to miss 5 real issues.
Return ONLY the JSON array with no preamble or explanation.
""")

        return "\n".join(prompt_parts)

    async def generate_remediation(
        self, findings: list[FindingResult], context: AssessmentContext
    ) -> list[FindingResult]:
        """Generate remediation suggestions for findings that lack them"""
        findings_needing_remediation = [f for f in findings if not f.suggestion_draft]

        if not findings_needing_remediation:
            return findings

        prompt = self._build_remediation_prompt(findings_needing_remediation, context)

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=(
                        "You are Clyira's Remediation Engine. Generate specific, actionable remediation "
                        "suggestions for quality document findings. Be practical and reference industry standards."
                    ),
                    temperature=0.2,
                    max_output_tokens=self.max_tokens,
                ),
            )
            remediation_data = self._parse_remediation_response(response.text)
            for i, finding in enumerate(findings_needing_remediation):
                if i < len(remediation_data):
                    finding.suggestion_draft = remediation_data[i].get("suggestion", "")
                    finding.next_step_text = remediation_data[i].get("next_step", "")

        except Exception as e:
            logger.error(f"Remediation generation failed: {e}")

        return findings

    def _build_remediation_prompt(self, findings: list[FindingResult], context: AssessmentContext) -> str:
        prompt = f"Document type: {context.document_category}\n\nFindings needing remediation:\n\n"
        for i, f in enumerate(findings):
            prompt += f"{i+1}. [{f.level}] {f.severity.upper()} — {f.title}\n"
            prompt += f"   Description: {f.description}\n"
            prompt += f"   Citation: {f.regulatory_citation}\n\n"

        prompt += """For each finding, provide:
1. suggestion_draft: Specific text/content to fix the issue
2. next_step: Immediate action the user should take

Return as JSON array: [{"suggestion": "...", "next_step": "..."}]"""
        return prompt

    def _parse_findings_response(self, response_text: str, level: str) -> list[FindingResult]:
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]
        json_text = json_text.strip()

        # Try clean parse first
        try:
            data = json.loads(json_text)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            # Response was truncated — recover complete objects by extracting individual {...} blocks
            data = []
            depth = 0
            start = None
            for i, ch in enumerate(json_text):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start is not None:
                        try:
                            obj = json.loads(json_text[start:i + 1])
                            data.append(obj)
                        except json.JSONDecodeError:
                            pass
                        start = None
            if not data:
                logger.warning(f"Could not recover any findings from truncated LLM response for {level}")
                return []
            logger.info(f"Recovered {len(data)} findings from truncated response for {level}")

        findings = []
        for item in data:
            if not item.get("title") or not item.get("description"):
                continue
            findings.append(FindingResult(
                level=item.get("level", level),
                severity=item.get("severity", "medium"),
                category=item.get("category", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                evidence=item.get("evidence", ""),
                location=item.get("location", ""),
                regulatory_citation=item.get("regulatory_citation", ""),
                citation_type=item.get("citation_type", ""),
                agency=item.get("agency", ""),
                suggestion_draft=item.get("suggestion_draft", ""),
                confidence_score=item.get("confidence_score", 0.7),
                validated=False,
            ))
        return findings

    def _parse_remediation_response(self, response_text: str) -> list[dict]:
        try:
            json_text = response_text
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]
            return json.loads(json_text.strip())
        except (json.JSONDecodeError, IndexError):
            return []

    @staticmethod
    def _get_level_name(level: str) -> str:
        names = {
            "L1": "Structural Integrity",
            "L2": "Document Control",
            "L3": "Content Quality",
            "L4": "ALCOA+ Data Integrity",
            "L5": "Data Intelligence",
            "L6": "Cross-Document Consistency",
            "L7": "Lifecycle Compliance",
            "L8": "Regulatory Gap Analysis",
            "L9": "Enforcement Risk",
            "L10": "Longitudinal Intelligence",
            "L11": "Submission Readiness",
        }
        return names.get(level, level)
