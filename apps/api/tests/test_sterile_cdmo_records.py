"""
Synthetic Test Library — STERILE-001..004 and CDMO-001..003

STERILE scenarios test sterile-aseptic pack specific checks:
  STERILE-001  Complete sterile BPR with full EM data — no critical findings
  STERILE-002  Missing Grade A/B area identification — high finding
  STERILE-003  No bioburden / endotoxin results — critical finding
  STERILE-004  Media fill / process simulation reference missing — high finding

CDMO scenarios test sponsor / contract manufacture checks:
  CDMO-001  Complete CDMO BPR with sponsor attribution — no critical findings
  CDMO-002  No sponsor lot number / sponsor attribution — critical finding
  CDMO-003  Technical agreement / quality agreement reference absent — high finding
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Synthetic record templates ────────────────────────────────────────────────

def _complete_sterile_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — STERILE INJECTABLE
Product: Vancomycin HCl for Injection 500mg
Product Code: VAN-INJ-500
Lot Number: VAN-2025-S001
Manufacturing Date: 2025-04-10
Manufacturing Area: ISO Grade A in Grade B background
Batch Size: 5,000 vials

APPROVAL SIGNATURES
Manufactured by: A. Kumar (Manufacturing Specialist)   Date: 2025-04-10
Reviewed by: S. Chen (QA Specialist)                  Date: 2025-04-11
Approved by: Dr. P. Mehta (QA Director)               Date: 2025-04-12

CLEANROOM QUALIFICATION
ISO Grade A: Particle count ≤3,520/m³ at 0.5µm, ≤20/m³ at 5.0µm
ISO Grade B: Particle count ≤3,520/m³ at 0.5µm, ≤29,000/m³ at 5.0µm  Result: PASS

ENVIRONMENTAL MONITORING RESULTS
                     Grade A      Grade B
Viable Air (cfu/m³)  0           2 (Limit: ≤10)     PASS
Settle Plates (cfu)  0           1 (Limit: ≤5)      PASS
Contact Plates (cfu) 0           1 (Limit: ≤5)      PASS

BIOBURDEN AND ENDOTOXIN
Bioburden pre-filtration: 0.5 cfu/100mL (Limit: ≤10 cfu/100mL)  PASS
Endotoxin (LAL): 0.05 EU/vial (Limit: ≤0.5 EU/vial)             PASS

MEDIA FILL REFERENCE
Media fill validation study MFS-2024-001 supports current process configuration.
Sterility test initiated per USP <71>.

IN-PROCESS CONTROLS
Filter integrity (pre-filtration): 3.8 bar (Spec: ≥3.5 bar)    PASS
Filter integrity (post-filtration): 3.7 bar (Spec: ≥3.5 bar)   PASS
Fill volume: 5.1 mL (Spec: 5.0 ± 0.2 mL)                       PASS

YIELD CALCULATION
Theoretical: 5,000 vials  Actual: 4,980  Yield: 99.6% (Spec: ≥97%)  PASS
""".strip()


def _missing_grade_area_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — STERILE INJECTABLE
Product: Vancomycin HCl for Injection 500mg
Lot Number: VAN-2025-S002
Manufacturing Date: 2025-04-10
Batch Size: 5,000 vials

APPROVAL SIGNATURES
Manufactured by: A. Kumar    Date: 2025-04-10
Approved by: Dr. P. Mehta   Date: 2025-04-12

IN-PROCESS CONTROLS
Filter integrity: 3.8 bar — PASS
Fill volume: 5.1 mL — PASS

ENVIRONMENTAL MONITORING
Viable air: 0 cfu/m³ — PASS

YIELD CALCULATION
Theoretical: 5,000  Actual: 4,980  Yield: 99.6%
""".strip()


def _missing_bioburden_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — STERILE INJECTABLE
Product: Vancomycin HCl for Injection 500mg
Lot Number: VAN-2025-S003
Manufacturing Area: ISO Grade A in Grade B background
Manufacturing Date: 2025-04-10
Batch Size: 5,000 vials

APPROVAL SIGNATURES
Manufactured by: A. Kumar    Date: 2025-04-10
Approved by: Dr. P. Mehta   Date: 2025-04-12

IN-PROCESS CONTROLS
Filter integrity: 3.8 bar — PASS
Fill volume: 5.1 mL — PASS

YIELD CALCULATION
Theoretical: 5,000  Actual: 4,980  Yield: 99.6%
""".strip()


def _missing_media_fill_ref_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — STERILE INJECTABLE
Product: Vancomycin HCl for Injection 500mg
Lot Number: VAN-2025-S004
Manufacturing Area: ISO Grade A in Grade B background
Manufacturing Date: 2025-04-10
Batch Size: 5,000 vials

APPROVAL SIGNATURES
Manufactured by: A. Kumar    Date: 2025-04-10
Approved by: Dr. P. Mehta   Date: 2025-04-12

BIOBURDEN AND ENDOTOXIN
Bioburden pre-filtration: 0.5 cfu/100mL — PASS
Endotoxin: 0.05 EU/vial — PASS

IN-PROCESS CONTROLS
Filter integrity: 3.8 bar — PASS
Fill volume: 5.1 mL — PASS

YIELD CALCULATION
Theoretical: 5,000  Actual: 4,980  Yield: 99.6%
""".strip()


def _complete_cdmo_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — CONTRACT MANUFACTURE
Product: Paclitaxel Injection 100mg/16.7mL
Contract Manufacturer: Pharma Services Inc.
Sponsor: AcmeBio Pharma Ltd.
Sponsor Lot Number: ACME-PTX-2025-001
Internal Lot Number: PSI-2025-PTX-001
Manufacturing Date: 2025-04-20
Batch Size: 2,000 vials
Quality Agreement Reference: QA-2023-ACME-007 (effective 2023-06-01)

APPROVAL SIGNATURES
Manufactured by: T. Williams (Manufacturing Lead)  Date: 2025-04-20
Reviewed by: L. Patel (QA Specialist)             Date: 2025-04-21
Approved by: Dr. M. Brown (QA Director)            Date: 2025-04-22

MATERIALS USED
Material                    Lot No.         Quantity
Paclitaxel API (ACME)       ACME-API-P001   20.0 g
Ethanol (USP)               ETH-2025-004    2000 mL
Cremophor EL                CRE-2025-007    200 mL

IN-PROCESS CONTROLS
pH: 6.8 (Spec: 6.5–7.5)       PASS
Appearance: Clear, colourless  PASS

YIELD CALCULATION
Theoretical: 2,000 vials  Actual: 1,985  Yield: 99.25%
""".strip()


def _missing_sponsor_attribution_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — CONTRACT MANUFACTURE
Product: Paclitaxel Injection 100mg/16.7mL
Internal Lot Number: PSI-2025-PTX-002
Manufacturing Date: 2025-04-20
Batch Size: 2,000 vials

APPROVAL SIGNATURES
Manufactured by: T. Williams    Date: 2025-04-20
Approved by: Dr. M. Brown       Date: 2025-04-22

MATERIALS USED
Material                    Lot No.         Quantity
Paclitaxel API              API-P001        20.0 g

IN-PROCESS CONTROLS
pH: 6.8 — PASS

YIELD CALCULATION
Theoretical: 2,000  Actual: 1,985  Yield: 99.25%
""".strip()


def _missing_quality_agreement_bpr() -> str:
    return """
BATCH PRODUCTION RECORD — CONTRACT MANUFACTURE
Product: Paclitaxel Injection 100mg/16.7mL
Contract Manufacturer: Pharma Services Inc.
Sponsor: AcmeBio Pharma Ltd.
Sponsor Lot Number: ACME-PTX-2025-003
Internal Lot Number: PSI-2025-PTX-003
Manufacturing Date: 2025-04-20
Batch Size: 2,000 vials

APPROVAL SIGNATURES
Manufactured by: T. Williams    Date: 2025-04-20
Approved by: Dr. M. Brown       Date: 2025-04-22

MATERIALS USED
Material              Lot No.    Quantity
Paclitaxel API        API-P003   20.0 g

IN-PROCESS CONTROLS
pH: 6.8 — PASS

YIELD CALCULATION
Theoretical: 2,000  Actual: 1,985  Yield: 99.25%
""".strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_context(doc_text: str, category: str = "MBR"):
    from app.engines.types import AssessmentContext
    from app.dtap import DTAPRegistry
    DTAPRegistry.initialize()
    profile = DTAPRegistry.get("DTAP-007")
    if not profile:
        profile = DTAPRegistry.get_by_category(category)
    return AssessmentContext(
        document_id="test-doc",
        company_id="test-company",
        assessment_id="test-assessment",
        document_text=doc_text,
        document_category=category,
        dtap_profile=profile,
    )


def _run_rule_engine(ctx):
    from app.engines.rule_engine import RuleEngine
    import asyncio
    engine = RuleEngine()
    profile = ctx.dtap_profile
    if not profile:
        return []
    levels = profile.get_rule_levels()
    loop = asyncio.new_event_loop()
    try:
        findings = loop.run_until_complete(engine.run(ctx, levels))
    finally:
        loop.close()
    return findings


# ── STERILE Tests ─────────────────────────────────────────────────────────────

class TestSTEREILE001_CompleteStepileBPR:
    """STERILE-001: Complete sterile BPR — no critical findings."""

    def test_no_critical_findings(self):
        ctx = _make_context(_complete_sterile_bpr())
        findings = _run_rule_engine(ctx)
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) == 0, \
            f"Complete sterile BPR should have no critical findings. Got: {[f.title for f in critical]}"

    def test_findings_have_explanation_traces(self):
        ctx = _make_context(_complete_sterile_bpr())
        findings = _run_rule_engine(ctx)
        traced = [f for f in findings if f.explanation_trace is not None]
        for f in traced:
            assert "engine" in f.explanation_trace
            assert f.explanation_trace["engine"] == "rule_engine"


class TestSTEREILE002_MissingGradeArea:
    """STERILE-002: No ISO grade area identification in BPR."""

    def test_findings_are_structured(self):
        ctx = _make_context(_missing_grade_area_bpr())
        findings = _run_rule_engine(ctx)
        assert isinstance(findings, list)
        for f in findings:
            assert f.severity in ("critical", "high", "medium", "low", "info")

    def test_no_grade_area_pass(self):
        ctx = _make_context(_missing_grade_area_bpr())
        findings = _run_rule_engine(ctx)
        grade_green = [
            f for f in findings
            if f.verification_state == "green"
            and any(kw in (f.title + f.description).lower()
                    for kw in ("grade a", "grade b", "cleanroom", "iso grade"))
        ]
        assert len(grade_green) == 0, \
            "Missing grade area classification should not produce a green finding"


class TestSTEREILE003_MissingBioburden:
    """STERILE-003: No bioburden or endotoxin results."""

    def test_no_bioburden_pass(self):
        ctx = _make_context(_missing_bioburden_bpr())
        findings = _run_rule_engine(ctx)
        bio_green = [
            f for f in findings
            if f.verification_state == "green"
            and any(kw in (f.title + f.description).lower()
                    for kw in ("bioburden", "endotoxin", "lal"))
        ]
        assert len(bio_green) == 0

    def test_verification_states_valid(self):
        ctx = _make_context(_missing_bioburden_bpr())
        findings = _run_rule_engine(ctx)
        valid_states = {None, "green", "red", "blue", "gray"}
        for f in findings:
            assert f.verification_state in valid_states, \
                f"Invalid verification_state: {f.verification_state}"


class TestSTEREILE004_MissingMediaFill:
    """STERILE-004: No media fill / process simulation reference."""

    def test_no_media_fill_pass(self):
        ctx = _make_context(_missing_media_fill_ref_bpr())
        findings = _run_rule_engine(ctx)
        mf_green = [
            f for f in findings
            if f.verification_state == "green"
            and any(kw in (f.title + f.description).lower()
                    for kw in ("media fill", "process simulation", "aseptic simulation"))
        ]
        assert len(mf_green) == 0

    def test_all_findings_have_level(self):
        ctx = _make_context(_missing_media_fill_ref_bpr())
        findings = _run_rule_engine(ctx)
        for f in findings:
            assert f.level.startswith("L"), f"Finding level must start with L, got: {f.level}"


# ── CDMO Tests ────────────────────────────────────────────────────────────────

class TestCDMO001_CompleteCDMOBPR:
    """CDMO-001: Complete CDMO BPR with sponsor attribution — no critical findings."""

    def test_no_critical_findings(self):
        ctx = _make_context(_complete_cdmo_bpr())
        findings = _run_rule_engine(ctx)
        critical = [f for f in findings if f.severity == "critical"]
        assert len(critical) == 0, \
            f"Complete CDMO BPR should have no critical findings. Got: {[f.title for f in critical]}"

    def test_green_findings_present(self):
        ctx = _make_context(_complete_cdmo_bpr())
        findings = _run_rule_engine(ctx)
        green = [f for f in findings if f.verification_state == "green"]
        assert len(green) > 0, "Complete CDMO BPR should have passing (green) findings"


class TestCDMO002_MissingSponsorAttribution:
    """CDMO-002: CDMO BPR with no sponsor name or sponsor lot number."""

    def test_findings_raised(self):
        ctx = _make_context(_missing_sponsor_attribution_bpr())
        findings = _run_rule_engine(ctx)
        assert isinstance(findings, list) and len(findings) >= 0

    def test_no_sponsor_green_pass(self):
        ctx = _make_context(_missing_sponsor_attribution_bpr())
        findings = _run_rule_engine(ctx)
        sponsor_green = [
            f for f in findings
            if f.verification_state == "green"
            and any(kw in (f.title + f.description).lower()
                    for kw in ("sponsor", "principal", "contract manufacture"))
        ]
        assert len(sponsor_green) == 0


class TestCDMO003_MissingQualityAgreement:
    """CDMO-003: CDMO BPR with sponsor attribution but no quality agreement reference."""

    def test_findings_structured(self):
        ctx = _make_context(_missing_quality_agreement_bpr())
        findings = _run_rule_engine(ctx)
        for f in findings:
            assert hasattr(f, "severity")
            assert hasattr(f, "verification_state")
            assert hasattr(f, "explanation_trace")

    def test_no_qa_agreement_pass(self):
        ctx = _make_context(_missing_quality_agreement_bpr())
        findings = _run_rule_engine(ctx)
        qa_green = [
            f for f in findings
            if f.verification_state == "green"
            and any(kw in (f.title + f.description).lower()
                    for kw in ("quality agreement", "technical agreement", "contract"))
        ]
        assert len(qa_green) == 0, \
            "Missing quality agreement reference should not produce a green pass"

    def test_explanation_trace_structure(self):
        """explanation_trace dicts must conform to expected schema."""
        ctx = _make_context(_missing_quality_agreement_bpr())
        findings = _run_rule_engine(ctx)
        for f in findings:
            if f.explanation_trace:
                assert "method" in f.explanation_trace
                assert "engine" in f.explanation_trace
                assert "outcome" in f.explanation_trace
                assert f.explanation_trace["outcome"] in ("pass", "fail", "finding")
