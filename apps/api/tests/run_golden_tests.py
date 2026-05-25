"""
Golden Test Runner — Rule Engine Regression Tests
==================================================
Runs the rule engine against synthetic test documents and checks that
expected findings are produced (and forbidden findings are not).

Run from apps/api/:
    python tests/run_golden_tests.py

Exit code 0 = all tests pass, 1 = failures.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add apps/api to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dtap import DTAPRegistry
from app.engines.rule_engine import RuleEngine
from app.engines.types import AssessmentContext


FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PATH = FIXTURES / "golden_answers.json"
DOCS_DIR = FIXTURES / "documents"


def _build_context(doc_text: str, doc_category: str, dtap_id: str) -> AssessmentContext:
    DTAPRegistry.initialize()
    profile = DTAPRegistry.get(dtap_id)
    if not profile:
        profile = DTAPRegistry.get_by_category(doc_category)

    return AssessmentContext(
        document_id="test-doc-id",
        company_id="test-company-id",
        assessment_id="test-assessment-id",
        document_text=doc_text,
        document_sections={},
        document_category=doc_category,
        dtap_profile=profile,
        company_agencies=["FDA"],
        company_sub_sectors=["SS-D1"],
        regulatory_frameworks=["21 CFR"],
        user_references=[],
        enforcement_records=[],
        historical_assessments=[],
    )


def _check_finding_present(findings: list, requirement: dict) -> tuple[bool, str]:
    """Return (found, reason_string)."""
    level = requirement.get("level")
    category = requirement.get("category", "")
    contains_text = requirement.get("contains_text", "")

    for f in findings:
        if level and f.level != level:
            continue
        if category and category not in (f.category or ""):
            continue
        if contains_text:
            combined = (f.title or "") + " " + (f.description or "") + " " + (f.evidence or "")
            if contains_text.lower() not in combined.lower():
                continue
        return True, ""

    desc = f"level={level}, category={category}"
    if contains_text:
        desc += f", contains='{contains_text}'"
    return False, f"No finding matched: {desc}"


def _check_finding_absent(findings: list, forbidden: dict) -> tuple[bool, str]:
    """Return (absent=True means OK, reason_string)."""
    category = forbidden.get("category", "")
    for f in findings:
        if category and category in (f.category or ""):
            return False, f"Forbidden finding present: category={category} — {f.title}"
    return True, ""


async def run_test(name: str, spec: dict) -> dict:
    """Run one document test. Returns result dict."""
    # document_path in golden_answers.json is relative to apps/api/
    doc_path = Path(__file__).parent.parent / spec["document_path"]
    if not doc_path.exists():
        return {"name": name, "passed": False, "errors": [f"Document not found: {doc_path}"]}

    doc_text = doc_path.read_text(encoding="utf-8")
    doc_category = spec["document_category"]
    dtap_id = spec["dtap_id"]

    ctx = _build_context(doc_text, doc_category, dtap_id)
    if not ctx.dtap_profile:
        return {"name": name, "passed": False, "errors": [f"DTAP profile not found: {dtap_id}"]}

    engine = RuleEngine()
    rule_levels = ctx.dtap_profile.get_rule_levels()
    findings = await engine.run(ctx, rule_levels)

    errors = []

    # Check required findings
    for req in spec.get("required_findings", []):
        found, reason = _check_finding_present(findings, req)
        if not found:
            errors.append(f"MISSING: {req.get('reason', '')} — {reason}")

    # Check forbidden findings
    for forbidden in spec.get("forbidden_findings", []):
        ok, reason = _check_finding_absent(findings, forbidden)
        if not ok:
            errors.append(f"FORBIDDEN FINDING PRESENT: {forbidden.get('reason', '')} — {reason}")

    return {
        "name": name,
        "passed": len(errors) == 0,
        "errors": errors,
        "findings_count": len(findings),
        "findings_summary": {
            level: [
                {"category": f.category, "severity": f.severity, "title": f.title[:60]}
                for f in findings if f.level == level
            ]
            for level in sorted({f.level for f in findings})
        },
    }


async def main():
    print("Clyira Rule Engine — Golden Tests")
    print("=" * 60)

    golden = json.loads(GOLDEN_PATH.read_text())
    test_specs = {k: v for k, v in golden.items() if not k.startswith("_")}

    results = []
    for name, spec in test_specs.items():
        print(f"\nRunning: {name}...")
        result = await run_test(name, spec)
        results.append(result)

        count = result.get("findings_count", 0)
        if result["passed"]:
            print(f"  PASS — {count} findings produced")
        else:
            print(f"  FAIL — {count} findings produced")
            for err in result["errors"]:
                print(f"    ✗ {err}")

        if result.get("findings_summary"):
            for level, level_findings in result["findings_summary"].items():
                for f in level_findings:
                    marker = "  " if result["passed"] else "  "
                    print(f"    [{level}] {f['severity']:8} {f['category']:35} {f['title']}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} tests passed")

    if passed < total:
        print("\nFailed tests:")
        for r in results:
            if not r["passed"]:
                print(f"  {r['name']}: {r['errors']}")
        sys.exit(1)
    else:
        print("All golden tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
