"""
LLM Engine — multi-provider semantic analysis.
Primary: Groq (LLaMA 3.3 70B) — 14,400 req/day free, 30 RPM.
Fallback: Gemini — used when no Groq key is set.
Handles: L3 (Content Quality), L6 (Cross-Doc Consistency), L8 (Regulatory Gap),
         L10 (Longitudinal Intelligence), and remediation generation.
"""
import json
import logging
import httpx

from app.core.config import settings
from app.engines.types import AssessmentContext, FindingResult

logger = logging.getLogger(__name__)

GEMINI_V1_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _llm_available() -> bool:
    return bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY)


def _active_model() -> str:
    return settings.GROQ_MODEL if settings.GROQ_API_KEY else settings.GEMINI_MODEL


async def _call_groq(system_prompt: str, user_prompt: str) -> str:
    """Call Groq (LLaMA) via OpenAI-compatible API. Retries on TPM 429 and 529 overload; fails fast on daily quota."""
    import asyncio
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": settings.GEMINI_MAX_TOKENS,
    }
    for attempt in range(4):
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json=payload,
            )
            if resp.status_code == 429:
                body = resp.text.lower()
                if "day" in body or "daily" in body or "quota" in body:
                    raise Exception("Groq daily quota exhausted")
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s — TPM resets every minute
                print(f"  Groq 429 TPM limit (attempt {attempt+1}/4), waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 529:
                # Groq service overloaded — back off and retry
                wait = 10 * (attempt + 1)  # 10s, 20s, 30s, 40s
                print(f"  Groq 529 overloaded (attempt {attempt+1}/4), waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    raise Exception("Groq service unavailable after 4 attempts (429/529)")


async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini REST API. Retries on RPM limits; fails fast on daily quota exhaustion."""
    import asyncio
    url = GEMINI_V1_URL.format(model=settings.GEMINI_MODEL)
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": settings.GEMINI_MAX_TOKENS,
        },
    }
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
            )
            if resp.status_code == 429:
                body = resp.text.lower()
                if "quota" in body or "daily" in body or "exceeded" in body:
                    raise Exception("Gemini daily quota exhausted — assessment will complete with rule-only findings")
                wait = 5 * (2 ** attempt)  # 5s, 10s, 20s
                print(f"  Gemini 429 RPM limit (attempt {attempt+1}/3), waiting {wait}s...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError(f"Gemini returned no candidates: {data.get('promptFeedback', data)}")
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise ValueError(f"Gemini candidate has no parts (finish_reason={candidates[0].get('finishReason')})")
            return parts[0]["text"]
    raise Exception("Gemini RPM rate limit: failed after 3 attempts")


async def _call_llm(system_prompt: str, user_prompt: str) -> str:
    """Route to Groq (primary) or Gemini (fallback). Falls back to Gemini if Groq is overloaded."""
    if settings.GROQ_API_KEY:
        try:
            return await _call_groq(system_prompt, user_prompt)
        except Exception as e:
            err = str(e).lower()
            # If Groq is overloaded or exhausted, try Gemini before giving up
            if settings.GEMINI_API_KEY and ("unavailable" in err or "529" in err or "overload" in err):
                print(f"  Groq failed ({e}), falling back to Gemini...")
                return await _call_gemini(system_prompt, user_prompt)
            raise
    if settings.GEMINI_API_KEY:
        return await _call_gemini(system_prompt, user_prompt)
    raise ValueError("No LLM API key configured — set GROQ_API_KEY or GEMINI_API_KEY")


class LLMEngine:
    """
    Semantic analysis engine powered by Gemini v1 REST API.
    Uses structured prompts with DTAP context for precise assessment.
    """

    async def run_checks_batched(self, checks_by_level: dict[str, list[str]], context: AssessmentContext) -> list[FindingResult]:
        """Evaluate ALL unimplemented rule checks across multiple levels in ONE LLM call."""
        if not _llm_available():
            return []
        profile = context.dtap_profile

        prompt_parts = [
            f"## Multi-Level Document Assessment — Rule Checks",
            f"Document type: {profile.document_category} (DTAP: {profile.dtap_id})",
            f"",
            f"### Checks to perform (grouped by level):",
        ]
        for level, checks in checks_by_level.items():
            prompt_parts.append(f"\n**{level} — {self._get_level_name(level)}:**")
            for check in checks:
                prompt_parts.append(f"- {check.replace('_', ' ').title()}")

        prompt_parts.append(f"\n### Document Content:\n{context.document_text[:20000]}")
        prompt_parts.append(f"\nApplicable agencies: {', '.join(context.company_agencies)}")
        if context.regulatory_frameworks:
            prompt_parts.append(f"Regulatory frameworks: {', '.join(context.regulatory_frameworks)}")
        prompt_parts.append("""
### Output Instructions:
Identify ALL gaps and non-conformances for each check above.
Each finding MUST include the correct "level" field (matching the level heading above, e.g. "L1", "L2").
Return ONLY a JSON array of findings with no preamble.
""")

        system = self._get_system_prompt("Multi-Level", profile.document_category)
        total_checks = sum(len(v) for v in checks_by_level.values())
        print(f"  LLM [{_active_model()}]: batched rule fallback for {list(checks_by_level.keys())} ({total_checks} checks)...")
        try:
            text = await _call_llm(system, "\n".join(prompt_parts))
            findings = self._parse_findings_response(text, list(checks_by_level.keys())[0])
            print(f"  LLM: batched rule fallback → {len(findings)} findings")
            return findings
        except Exception as e:
            logger.error(f"Batched rule fallback failed: {e}")
            print(f"  LLM ERROR [batched rule]: {type(e).__name__}: {e}")
            return []

    async def run(self, context: AssessmentContext, levels: list[str]) -> list[FindingResult]:
        """Run LLM assessment for all enabled levels in ONE batched call."""
        enabled_levels = [
            l for l in levels
            if context.dtap_profile.levels.get(l) and
               context.dtap_profile.levels[l].enabled and
               context.dtap_profile.levels[l].engine in ("llm", "hybrid")
        ]
        if not enabled_levels:
            return []

        print(f"  LLM: batched assessment for {enabled_levels}...")
        findings = await self._assess_levels_batched(enabled_levels, context)
        print(f"  LLM: {len(findings)} findings across {len(enabled_levels)} levels")
        return findings

    async def _assess_levels_batched(self, levels: list[str], context: AssessmentContext) -> list[FindingResult]:
        """Assess all LLM/hybrid levels in a SINGLE LLM call."""
        if not _llm_available():
            return []
        profile = context.dtap_profile

        prompt_parts = [
            f"## Document Under Assessment",
            f"Category: {profile.document_category} (DTAP: {profile.dtap_id})",
            f"",
            f"### Assessment Levels and Checks:",
        ]
        for level in levels:
            level_config = profile.levels[level]
            prompt_parts.append(f"\n**{level} — {self._get_level_name(level)}:**")
            for check in level_config.checks:
                prompt_parts.append(f"- {check.replace('_', ' ').title()}")

        prompt_parts.append(f"\n### Document Content:\n{context.document_text[:20000]}")

        if "L8" in levels and context.regulatory_context:
            prompt_parts.append("\n### Regulatory Requirements (for L8):")
            for reg in context.regulatory_context[:10]:
                prompt_parts.append(f"- [{reg.get('citation_reference', '')}] {reg.get('text', reg.get('content', ''))[:200]}")

        if context.user_references:
            prompt_parts.append("\n### Organization References:")
            for ref in context.user_references[:5]:
                prompt_parts.append(f"- {ref.get('title', '')}: {ref.get('extracted_text', '')[:300]}")

        if context.company_agencies:
            prompt_parts.append(f"\nApplicable agencies: {', '.join(context.company_agencies)}")
        if context.regulatory_frameworks:
            prompt_parts.append(f"Regulatory frameworks: {', '.join(context.regulatory_frameworks)}")

        prompt_parts.append("""
### Critical Output Instructions:
Each finding MUST include the correct "level" field (e.g., "L3", "L6", "L8", "L10").
Be THOROUGH — aim for 8-12 findings per level. Do NOT self-censor. A pharmaceutical document assessed by an FDA inspector should yield many observations.
Include critical/high severity findings for major gaps AND medium/low for minor ones.
Return ALL findings for ALL levels in a single JSON array. No preamble or explanation.
""")

        domain_block = self._get_domain_system_prompt(profile.document_category)
        system_prompt = f"""You are a senior FDA/EMA regulatory assessor performing a MULTI-LEVEL assessment of a pharmaceutical quality document.

YOUR MANDATE: Find ALL issues — gaps, ambiguities, missing elements, weak language, non-conformances, data integrity risks.

SEVERITY: critical (Warning Letter), high (483 obs), medium (internal audit), low (best practice), info (advisory).

TAG every finding with its correct level (L3, L5, L6, L8, L9, L10, or L11).
{domain_block}
OUTPUT: Single JSON array. Each item: {{"level":"...","severity":"...","category":"...","title":"...","description":"...","evidence":"...","regulatory_citation":"...","citation_type":"...","agency":"...","suggestion_draft":"...","confidence_score":0.0}}"""

        print(f"  LLM [{_active_model()}]: batched assessment for {levels}...")
        try:
            text = await _call_llm(system_prompt, "\n".join(prompt_parts))
            findings = self._parse_findings_response(text, levels[0] if len(levels) == 1 else "?")
            return findings
        except Exception as e:
            logger.error(f"Batched LLM assessment failed: {type(e).__name__}: {e}")
            print(f"  LLM ERROR [batched]: {type(e).__name__}: {e}")
            return []

    async def _assess_level(self, level: str, context: AssessmentContext) -> list[FindingResult]:
        """Run LLM assessment for a single level (used by legacy per-level path)."""
        if not _llm_available():
            logger.warning(f"Skipping LLM assessment for {level} — no LLM key configured")
            return []

        system_prompt = self._get_system_prompt(level, context.document_category)
        user_prompt = self._build_assessment_prompt(level, context)

        try:
            text = await _call_llm(system_prompt, user_prompt)
            return self._parse_findings_response(text, level)
        except Exception as e:
            logger.error(f"LLM assessment failed for {level}: {type(e).__name__}: {e}")
            print(f"  LLM ERROR [{level}]: {type(e).__name__}: {e}")
            return []

    def _get_system_prompt(self, level: str, document_category: str = "") -> str:
        domain_block = self._get_domain_system_prompt(document_category) if document_category else ""
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
{domain_block}
OUTPUT FORMAT: Return a JSON array of ALL findings. Do not omit findings to save space.
Each finding: {{"level": "...", "severity": "...", "category": "...", "title": "...",
"description": "...", "evidence": "...", "location": "...",
"regulatory_citation": "...", "citation_type": "...", "agency": "...",
"suggestion_draft": "...", "confidence_score": 0.0}}"""

    def _get_domain_system_prompt(self, document_category: str) -> str:
        """Returns domain-specific assessment guidance appended to the base system prompt."""
        cat = document_category.upper()

        if cat == "DEVIATION":
            return """
DEVIATION REPORT — DOMAIN REQUIREMENTS (21 CFR 211.192, ICH Q10, EU GMP Ch 8):

DIMENSION CHECKS YOU MUST PERFORM:
1. Root Cause Quality: Is the stated root cause the actual systemic cause? Flag "human error" as root cause without systemic analysis — it is almost always a proximate, not root, cause.
2. Impact Evidence: Are impact assessment claims ("no impact on quality") supported by analytical data? Flag unsupported impact conclusions as high/critical.
3. Containment Documentation: Was immediate containment action documented with timing? Flag missing containment or containment documented days after the event.
4. CAPA Adequacy: Do CAPAs address the root cause or only the symptom? Flag training-only CAPAs for systemic failures.
5. Batch Disposition Justification: Is batch release/rejection justified with QA rationale and supporting data? A disposition without explicit justification is a 483 finding.
6. FAR Assessment: Is Field Alert Report (FAR) requirement assessed (even if "not applicable")? The absence of this assessment is a 483 observation under 21 CFR 314.81.
7. Timeliness: Was the deviation initiated within 24 hours for Critical deviations? Was the investigation closed within 30 days (Major) or 120 days (Critical)?
8. ALCOA+ Data Integrity: Are all data entries attributable, legible, contemporaneous, original, accurate? Flag retrospective entries, whitened-out data, missing dates.
9. Regulatory Reporting: Is regulatory reporting requirement assessed (e.g., Annual Report, field alert, supplement)?

CRITICAL PATTERNS TO ALWAYS FLAG:
- "No impact on product quality" without cited analytical test data → critical
- "Human error" as root cause without systemic analysis → high
- Training as the only CAPA action → high
- FAR assessment section absent entirely → high
- Disposition stated before investigation was complete → critical
- Batch released with confirmed critical deviation → critical"""

        if cat == "LIR":
            return """
LAB INVESTIGATION REPORT (OOS/OOT) — DOMAIN REQUIREMENTS (21 CFR 211.192, 211.194, FDA OOS Guidance 2006):

DIMENSION CHECKS YOU MUST PERFORM:
1. Phase I Structure: Phase I (laboratory investigation) MUST be present and documented BEFORE Phase II. Flag if Phase I is missing, incomplete, or its conclusion is absent.
2. Phase I Conclusion: Phase I must end with an explicit conclusion: either an assignable laboratory cause was found (and therefore original result is invalidated) OR no assignable cause was found (and therefore Phase II is required). Flag absence of this conclusion.
3. Phase II Adequacy: If Phase I found no assignable cause, Phase II (full-scale investigation) is MANDATORY. Flag if Phase II is absent when Phase I concluded no assignable cause.
4. Retest Documentation: All retests must be fully documented — analyst, instrument, date, results. Flag retest results referenced without documentation.
5. Assignable Cause Quality: An assignable cause MUST be a documented, demonstrated laboratory error (e.g., calculation error, instrument malfunction with records, analyst error witnessed). Flag "analyst error" or "instrument problem" without supporting evidence.
6. Passing Retest ≠ Assignable Cause: Passing retest results alone are NOT a valid basis for invalidating an OOS result (FDA OOS Guidance 2006 §IV.C). This is the #1 Warning Letter pattern. Flag any LIR that uses passing retests to justify invalidation without a demonstrated laboratory error.
7. Selective Reporting: If the LIR states N retests were performed but only M < N results are documented, flag as critical — selective reporting of test results.
8. Disposition Consistency: A confirmed OOS result (Phase II confirmed) cannot result in batch release without explicit QA justification and regulatory notification. Flag confirmed OOS + release as critical.
9. ALCOA+ Data Integrity: Flag missing analyst names on entries, undated results, retrospective completion, instrument logs not cross-referenced.

CRITICAL PATTERNS TO ALWAYS FLAG:
- Phase I missing entirely → critical
- Phase I conclusion absent (no explicit assignable/no-assignable statement) → high
- Passing retest used as sole invalidation justification → critical (21 CFR 211.192)
- Stated retest count does not match documented results → critical
- Phase II absent when Phase I found no assignable cause → critical
- Confirmed OOS result with batch released → critical
- Analyst error cited as assignable cause without witnessed/documented evidence → high"""

        if cat == "CAPA":
            return """
CAPA — DOMAIN REQUIREMENTS (21 CFR 820.100, ICH Q10 §3.2, ISO 13485 §8.5):

DIMENSION CHECKS YOU MUST PERFORM:
1. Root Cause Depth: Is the root cause analysis rigorous (5-Why, fishbone, FMEA)? Flag shallow analyses that stop at the proximate cause.
2. Human Error Analysis: "Human error" as root cause must be followed by analysis of WHY human error occurred (training gap, procedure clarity, workload, environment). Flag standalone human error conclusions.
3. Training-Only CAPAs: Training as the sole corrective action for systemic failures is a recurring 483 pattern. Flag unless root cause is genuinely a training gap.
4. Effectiveness Criteria: CAPA must include measurable effectiveness check criteria with a defined verification date. Flag absent or unmeasurable criteria.
5. Retrospective CAPA: Flag CAPAs opened after the problem recurred — indicates the original CAPA was ineffective.
6. OOS Invalidation Basis: If the CAPA references an OOS result, verify that the invalidation was based on a documented assignable cause, not merely passing retests.
7. Scope: Does the CAPA address only the immediate instance or the systemic/horizontal extent of the problem?"""

        if cat == "SOP":
            return """
SOP — DOMAIN REQUIREMENTS (21 CFR 211.68, 211.100, ICH Q10, EU GMP Ch 4):

DIMENSION CHECKS YOU MUST PERFORM:
1. Procedural Clarity: Are all steps numbered, unambiguous, and free of "as appropriate" / "if needed" without defined criteria?
2. Responsibility Assignment: Is each step's responsible role clearly named (not just "operator" generically)?
3. Critical Parameters: Are critical process parameters, acceptable ranges, and action limits explicitly stated?
4. Deviation Handling: Is the procedure for handling out-of-specification or unexpected results included?
5. Training Requirements: Are qualification requirements for personnel performing the procedure stated?
6. Review Cycle: Is the review frequency stated and consistent with the criticality of the procedure?"""

        if cat == "ATM":
            return """
ANALYTICAL TEST METHOD — DOMAIN REQUIREMENTS (21 CFR 211.194, ICH Q2(R1), USP <1225>):

DIMENSION CHECKS YOU MUST PERFORM:
1. System Suitability: Are system suitability criteria (resolution, tailing, RSD) defined with acceptance limits? Flag absent SST requirements.
2. Validation Parameters: Are all required validation parameters present (specificity, linearity, range, accuracy, precision, LOD, LOQ, robustness)?
3. Reference Standards: Are reference standard requirements (source, purity, storage, handling) documented?
4. OOS/Aberrant Result Procedure: Is the procedure for handling aberrant results and failing system suitability defined?
5. Instrument Qualification: Are instrument qualification requirements (IQ/OQ/PQ) referenced?"""

        return ""

    def _build_assessment_prompt(self, level: str, context: AssessmentContext) -> str:
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

        prompt_parts.append(f"\n### Document Content:")
        prompt_parts.append(context.document_text[:20000])

        if context.regulatory_context and level == "L8":
            prompt_parts.append("\n### Relevant Regulatory Requirements:")
            for reg in context.regulatory_context[:10]:
                prompt_parts.append(f"- [{reg.get('citation_reference', '')}] {reg.get('text', reg.get('content', ''))[:200]}")

        if context.user_references:
            prompt_parts.append("\n### Organization-Specific References:")
            for ref in context.user_references[:5]:
                prompt_parts.append(f"- {ref.get('title', 'Reference')}: {ref.get('extracted_text', '')[:500]}")

        if context.company_agencies:
            prompt_parts.append(f"\n### Applicable Agencies: {', '.join(context.company_agencies)}")

        if context.regulatory_frameworks:
            prompt_parts.append(f"\n### Regulatory Frameworks:")
            prompt_parts.append(f"Assess against: {', '.join(context.regulatory_frameworks)}")

        prompt_parts.append("""
### Output Instructions:
Return a comprehensive JSON array of ALL findings. Be thorough — aim for 15-25 findings per level.
Return ONLY the JSON array with no preamble or explanation.
""")

        return "\n".join(prompt_parts)

    async def generate_remediation(
        self, findings: list[FindingResult], context: AssessmentContext
    ) -> list[FindingResult]:
        """Generate remediation suggestions for findings that lack them (top 20 by severity)."""
        findings_needing_remediation = [f for f in findings if not f.suggestion_draft]
        if not findings_needing_remediation:
            return findings

        # Cap at 20 most critical findings to keep prompt size manageable
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        findings_needing_remediation = sorted(
            findings_needing_remediation,
            key=lambda f: severity_order.get(f.severity, 5)
        )[:20]

        prompt = self._build_remediation_prompt(findings_needing_remediation, context)
        try:
            text = await _call_llm(
                "You are Clyira's Remediation Engine. Generate specific, actionable remediation "
                "suggestions for quality document findings. Be practical and reference industry standards.",
                prompt,
            )
            remediation_data = self._parse_remediation_response(text)
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
        prompt += 'Return as JSON array: [{"suggestion": "...", "next_step": "..."}]'
        return prompt

    def _parse_findings_response(self, response_text: str, level: str) -> list[FindingResult]:
        json_text = response_text
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0]
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0]
        json_text = json_text.strip()

        try:
            data = json.loads(json_text)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            data = []
            depth, start = 0, None
            for i, ch in enumerate(json_text):
                if ch == "{":
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0 and start is not None:
                        try:
                            data.append(json.loads(json_text[start:i + 1]))
                        except json.JSONDecodeError:
                            pass
                        start = None
            if not data:
                logger.warning(f"Could not recover findings from LLM response for {level}")
                return []

        findings = []
        for item in data:
            # Handle MVP legacy field names alongside current names
            title = item.get("title") or item.get("finding_statement", "")
            description = item.get("description") or item.get("finding_statement", "")
            evidence = item.get("evidence") or item.get("text_excerpt", "")
            location = item.get("location") or item.get("section_reference", "")
            regulatory_citation = item.get("regulatory_citation") or item.get("primary_citation", "")

            # MVP used integer assessment_level (1–11) mapped to string "L{n}"
            raw_level = item.get("level") or item.get("assessment_level", level)
            if isinstance(raw_level, int):
                raw_level = f"L{raw_level}"

            if not title or not description:
                continue
            findings.append(FindingResult(
                level=str(raw_level),
                severity=item.get("severity", "medium"),
                category=item.get("category", ""),
                title=title,
                description=description,
                evidence=evidence,
                location=location,
                regulatory_citation=regulatory_citation,
                citation_type=item.get("citation_type", ""),
                agency=item.get("agency", ""),
                suggestion_draft=item.get("suggestion_draft", ""),
                confidence_score=float(item.get("confidence_score", 0.7)),
                validated=False,
                verification_state="blue",
                explanation_trace={
                    "method": "llm_semantic",
                    "engine": "llm_engine",
                    "level": str(raw_level),
                    "outcome": "finding",
                    "confidence": float(item.get("confidence_score", 0.7)),
                    "model": None,  # populated by assessment_service.provenance
                },
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
            "L1": "Structural Integrity", "L2": "Document Control",
            "L3": "Content Quality", "L4": "ALCOA+ Data Integrity",
            "L5": "Data Intelligence", "L6": "Cross-Document Consistency",
            "L7": "Lifecycle Compliance", "L8": "Regulatory Gap Analysis",
            "L9": "Enforcement Risk", "L10": "Longitudinal Intelligence",
            "L11": "Submission Readiness",
        }
        return names.get(level, level)
