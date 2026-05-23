"""
Assessment Orchestrator — Coordinates the full L1-L11 neuro-symbolic pipeline.
This is the core of Clyira's assessment engine.
"""
import time
import logging

from app.dtap import DTAPRegistry, DTAPProfile
from app.engines.types import AssessmentContext, FindingResult
from app.engines.rule_engine import RuleEngine
from app.engines.llm_engine import LLMEngine
from app.engines.enforcement_engine import EnforcementEngine
from app.engines.scoring import ScoringEngine
from app.engines.validator import AntiHallucinationGate

logger = logging.getLogger(__name__)


class AssessmentOrchestrator:
    """
    Orchestrates the full assessment pipeline.

    Pipeline:
    1. Load document content and resolve DTAP
    2. Load company context (agencies, references, Level 0)
    3. Run rule engine (L1, L2, L4, L5, L7, structural L11)
    4. Run LLM engine (L3, L6, L8) with RAG-retrieved regulatory context
    5. Run enforcement matching (L9)
    6. Run longitudinal analysis (L10)
    7. Apply anti-hallucination gate
    8. Calculate score
    9. Generate remediation suggestions
    10. Store results
    """

    def __init__(self):
        self.rule_engine = RuleEngine()
        self.llm_engine = LLMEngine()
        self.enforcement_engine = EnforcementEngine()
        self.scoring_engine = ScoringEngine()
        self.validator = AntiHallucinationGate()

    async def run_assessment(self, context: AssessmentContext) -> dict:
        """Execute the full assessment pipeline"""
        start_time = time.time()
        all_findings: list[FindingResult] = []

        # Resolve DTAP
        if not context.dtap_profile:
            context.dtap_profile = DTAPRegistry.resolve(
                context.document_category,
                context.company_sub_sectors[0] if context.company_sub_sectors else None,
            )

        if not context.dtap_profile:
            # Fall back to SOP profile for unknown document categories
            logger.warning(
                f"No DTAP for category '{context.document_category}', "
                f"falling back to SOP (DTAP-001)"
            )
            context.dtap_profile = DTAPRegistry.get("DTAP-001")
            if not context.dtap_profile:
                raise ValueError("DTAP registry not initialized — call DTAPRegistry.initialize() on startup")

        profile = context.dtap_profile
        logger.info(f"Running assessment with DTAP {profile.dtap_id} for {profile.document_category}")

        # Phase 1: Rule Engine (deterministic checks)
        rule_levels = profile.get_rule_levels()
        if rule_levels:
            logger.info(f"Phase 1: Rule engine for levels {rule_levels}")
            rule_findings = await self.rule_engine.run(context, rule_levels)
            all_findings.extend(rule_findings)

        # Phase 2: LLM Engine (semantic analysis with RAG)
        llm_levels = profile.get_llm_levels()
        if llm_levels:
            logger.info(f"Phase 2: LLM engine for levels {llm_levels}")
            llm_findings = await self.llm_engine.run(context, llm_levels)
            all_findings.extend(llm_findings)

        # Phase 3: Enforcement Matching (L9)
        if "L9" in profile.get_enabled_levels():
            logger.info("Phase 3: Enforcement matching")
            enforcement_findings = await self.enforcement_engine.run(
                context, all_findings
            )
            all_findings.extend(enforcement_findings)

            # Elevate severity for enforcement-matched findings
            all_findings = self.enforcement_engine.elevate_severities(
                all_findings, context.enforcement_records
            )

        # Phase 4: Anti-hallucination validation
        logger.info("Phase 4: Anti-hallucination gate")
        validated_findings = await self.validator.validate(all_findings, context)

        # Phase 5: Scoring
        logger.info("Phase 5: Calculating score")
        from app.engines.scoring import ScoringEngine
        score_result = self.scoring_engine.calculate(validated_findings, profile)

        # Phase 6: Generate remediation
        logger.info("Phase 6: Generating remediation suggestions")
        findings_with_remediation = await self.llm_engine.generate_remediation(
            validated_findings, context
        )

        processing_time = time.time() - start_time

        return {
            "assessment_id": context.assessment_id,
            "findings": findings_with_remediation,
            "score": score_result["score"],
            "score_band": score_result["score_band"],
            "level_scores": score_result["level_scores"],
            "data_integrity_hold": score_result.get("data_integrity_hold", False),
            "suspended_reason": score_result.get("suspended_reason"),
            "finding_counts": {
                "critical": sum(1 for f in validated_findings if f.severity == "critical"),
                "high": sum(1 for f in validated_findings if f.severity == "high"),
                "medium": sum(1 for f in validated_findings if f.severity == "medium"),
                "low": sum(1 for f in validated_findings if f.severity == "low"),
                "info": sum(1 for f in validated_findings if f.severity == "info"),
            },
            "enforcement_matches": sum(1 for f in validated_findings if f.enforcement_match),
            "processing_time_seconds": processing_time,
            "levels_run": profile.get_enabled_levels(),
        }
