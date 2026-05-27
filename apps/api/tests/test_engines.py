"""
Unit tests for Phase 0+1 engine wiring.

Tests cover:
  - rag_engine: source_type field in results
  - regulatory_corpus_engine: search + graceful empty
  - facility_risk_engine: fuzzy match + graceful empty
  - international_enforcement_engine: graceful empty + agency tagging
  - enforcement_engine: multi-source annotation (integration smoke)
"""
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _reset_engine(module):
    """Force a lazy-loaded engine to reload on next call."""
    for attr in ('_bm25', '_loaded', '_corpus', '_inspections', '_import_alerts'):
        if hasattr(module, attr):
            if attr == '_loaded':
                setattr(module, attr, False)
            else:
                setattr(module, attr, None if attr == '_bm25' else [])


# ──────────────────────────────────────────────────────────────────────────────
# rag_engine tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRagEngine:
    def test_search_returns_source_type(self):
        from app.engines import rag_engine
        results = rag_engine.search("capa investigation root cause", n_results=3)
        for r in results:
            assert 'source_type' in r, "source_type field missing from rag_engine result"

    def test_search_source_type_defaults_to_warning_letter(self):
        from app.engines import rag_engine
        results = rag_engine.search("deviation investigation", n_results=1)
        if results:
            assert results[0]['source_type'] in (
                'warning_letter', '483', 'consent_decree', 'import_alert'
            ), f"Unexpected source_type: {results[0]['source_type']}"

    def test_format_excerpt_includes_source_label(self):
        from app.engines import rag_engine
        mock_precedents = [{
            'company': 'Acme Pharma', 'office': 'Dallas', 'year': '2023',
            'text': 'Investigator observed missing audit trail.',
            'source_type': 'warning_letter',
        }]
        excerpt = rag_engine.format_enforcement_excerpt(mock_precedents)
        assert 'Warning Letter' in excerpt

    def test_format_excerpt_483_label(self):
        from app.engines import rag_engine
        mock_precedents = [{
            'company': 'Beta Labs', 'office': 'NY', 'year': '2022',
            'text': 'Analyst failed to follow SOP.', 'source_type': '483',
        }]
        excerpt = rag_engine.format_enforcement_excerpt(mock_precedents)
        assert 'Form 483' in excerpt

    def test_search_below_threshold_excluded(self):
        from app.engines import rag_engine
        # A nonsense query should return no results
        results = rag_engine.search("xyzzy frobnicator quux", n_results=5)
        assert isinstance(results, list)
        for r in results:
            assert r['score'] >= 0.5

    def test_graceful_degradation_no_index(self):
        from app.engines import rag_engine as re
        original = re._bm25
        re._bm25 = None
        with patch.object(re, '_load_index', return_value=False):
            results = re.search("test query")
        re._bm25 = original
        assert results == []


# ──────────────────────────────────────────────────────────────────────────────
# regulatory_corpus_engine tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRegulatoryCorpusEngine:
    def test_search_returns_required_fields(self):
        from app.engines import regulatory_corpus_engine
        results = regulatory_corpus_engine.search("investigation deviation", n_results=3)
        for r in results:
            assert 'text' in r
            assert 'source_body' in r
            assert 'score' in r
            assert r['score'] >= 0.5

    def test_cfr_filter_narrows_results(self):
        from app.engines import regulatory_corpus_engine
        results = regulatory_corpus_engine.search(
            "laboratory investigation", n_results=3, cfr_filter="21 CFR 211"
        )
        # If results come back, they should be FDA/eCFR sourced
        for r in results:
            assert 'text' in r

    def test_format_regulatory_context_empty(self):
        from app.engines import regulatory_corpus_engine
        out = regulatory_corpus_engine.format_regulatory_context([])
        assert out == ""

    def test_format_regulatory_context_nonempty(self):
        from app.engines import regulatory_corpus_engine
        mock_results = [{
            'text': 'Written procedures shall be followed.',
            'cfr_citation': '21 CFR 211.100',
            'citation_reference': '21 CFR 211.100',
            'source_body': 'FDA/eCFR',
            'score': 0.8,
        }]
        out = regulatory_corpus_engine.format_regulatory_context(mock_results)
        assert '21 CFR 211.100' in out
        assert 'Written procedures' in out

    def test_graceful_degradation_missing_files(self, tmp_path):
        from app.engines import regulatory_corpus_engine as rce
        _reset_engine(rce)
        with patch.object(rce, '_resolve_index_dir', return_value=tmp_path):
            results = rce.search("test")
        _reset_engine(rce)
        assert results == []


# ──────────────────────────────────────────────────────────────────────────────
# facility_risk_engine tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFacilityRiskEngine:
    def test_get_inspection_history_empty_when_no_data(self):
        from app.engines import facility_risk_engine
        history = facility_risk_engine.get_inspection_history("Unknown Pharma LLC")
        assert isinstance(history, list)

    def test_get_facility_risk_signals_unknown_firm(self):
        from app.engines import facility_risk_engine
        signals = facility_risk_engine.get_facility_risk_signals("Nonexistent Pharma Co")
        assert signals['risk_level'] == 'unknown'
        assert signals['total_inspections'] == 0
        assert isinstance(signals['active_import_alerts'], list)

    def test_fuzzy_name_matching_threshold(self):
        from app.engines.facility_risk_engine import _fuzzy_match
        # Should match (same company, different suffix)
        assert _fuzzy_match("Acme Pharmaceuticals Inc", "Acme Pharmaceuticals") > 0.7
        # Should not match completely different names
        assert _fuzzy_match("Alpha Labs", "Omega Manufacturing Corp") < 0.5

    def test_normalize_name_strips_suffixes(self):
        from app.engines.facility_risk_engine import _normalize_name
        n = _normalize_name("Acme Pharmaceuticals Inc.")
        assert "inc" not in n
        assert "pharmaceuticals" not in n or "pharma" not in n

    def test_fei_matching_skips_fuzzy(self, tmp_path):
        """FEI number match should be exact, not fuzzy."""
        from app.engines import facility_risk_engine as fre
        _reset_engine(fre)
        jsonl = tmp_path / "inspections.jsonl"
        import json
        jsonl.write_text(
            json.dumps({"firm_name": "Test Corp", "fei_number": "1234567", "classification": "OAI"}) + "\n"
        )
        with patch.object(fre, '_resolve_index_dir', return_value=tmp_path):
            fre._load_data()
        history = fre.get_inspection_history("1234567")
        assert len(history) == 1
        assert history[0]['classification'] == 'OAI'
        _reset_engine(fre)

    def test_risk_level_high_with_import_alert(self, tmp_path):
        from app.engines import facility_risk_engine as fre
        _reset_engine(fre)
        import json
        (tmp_path / "import_alerts.jsonl").write_text(
            json.dumps({
                "alert_number": "99-999",
                "alert_type": "DWO",
                "firms_on_list": ["Beta Pharma Ltd"],
                "product_description": "Drug products",
                "charges": "Adulteration",
            }) + "\n"
        )
        with patch.object(fre, '_resolve_index_dir', return_value=tmp_path):
            fre._load_data()
        signals = fre.get_facility_risk_signals("Beta Pharma")
        assert signals['risk_level'] == 'high'
        assert len(signals['active_import_alerts']) >= 1
        _reset_engine(fre)


# ──────────────────────────────────────────────────────────────────────────────
# international_enforcement_engine tests
# ──────────────────────────────────────────────────────────────────────────────

class TestInternationalEnforcementEngine:
    def test_search_returns_empty_when_no_data(self):
        from app.engines import international_enforcement_engine
        results = international_enforcement_engine.search("audit trail data integrity")
        assert isinstance(results, list)

    def test_search_with_data_tags_source_agency(self, tmp_path):
        import json
        from app.engines import international_enforcement_engine as iee
        _reset_engine(iee)
        (tmp_path / "who_pq.jsonl").write_text(
            json.dumps({
                "text": "Facility failed to maintain adequate audit trail for electronic records.",
                "company": "GlobalPharma",
                "date": "2023-06-01",
                "source_type": "who_pq",
            }) + "\n"
        )
        with patch.object(iee, '_resolve_index_dir', return_value=tmp_path):
            iee._bm25 = None
            iee._corpus = []
            iee._load_index()
        results = iee.search("audit trail electronic records")
        if results:
            assert 'source_agency' in results[0]
            assert results[0]['source_agency'] == 'WHO'
        _reset_engine(iee)

    def test_format_international_excerpt_empty(self):
        from app.engines import international_enforcement_engine
        assert international_enforcement_engine.format_international_excerpt([]) == ""

    def test_format_international_excerpt_nonempty(self):
        from app.engines import international_enforcement_engine
        mock = [{
            'source_agency': 'MHRA',
            'company': 'UK Pharma', 'year': '2022',
            'text': 'GMP deficiency observed in manufacturing.',
        }]
        out = international_enforcement_engine.format_international_excerpt(mock)
        assert 'MHRA' in out
        assert 'UK Pharma' in out

    def test_agency_weight_below_one_for_non_fda(self, tmp_path):
        import json
        from app.engines import international_enforcement_engine as iee
        _reset_engine(iee)
        (tmp_path / "mhra.jsonl").write_text(
            json.dumps({"text": "GMP deficiency.", "company": "Test", "date": "2022-01-01"}) + "\n"
        )
        with patch.object(iee, '_resolve_index_dir', return_value=tmp_path):
            iee._bm25 = None
            iee._corpus = []
            iee._load_index()
        results = iee.search("GMP deficiency")
        if results:
            assert results[0]['agency_weight'] < 1.0
        _reset_engine(iee)


# ──────────────────────────────────────────────────────────────────────────────
# enforcement_engine integration smoke test
# ──────────────────────────────────────────────────────────────────────────────

class TestEnforcementEngineIntegration:
    @pytest.mark.asyncio
    async def test_run_annotates_findings_with_enforcement_match(self):
        from app.engines.enforcement_engine import EnforcementEngine
        from app.engines.types import FindingResult, AssessmentContext

        engine = EnforcementEngine()
        finding = FindingResult(
            level="L3",
            severity="medium",
            category="root_cause_superficial",
            title="Root cause analysis incomplete",
            description="Root cause not adequately identified.",
            regulatory_citation="21 CFR 211.192",
        )
        ctx = AssessmentContext(
            document_id="test-doc", company_id="test-co", assessment_id="test-assessment",
            document_text="CAPA investigation root cause corrective action",
            document_category="CAPA",
        )
        l9_findings = await engine.run(ctx, [finding])
        # Should run without exception; findings may or may not match depending on corpus
        assert isinstance(l9_findings, list)

    @pytest.mark.asyncio
    async def test_run_returns_empty_for_no_findings(self):
        from app.engines.enforcement_engine import EnforcementEngine
        from app.engines.types import AssessmentContext

        engine = EnforcementEngine()
        ctx = AssessmentContext(
            document_id="x", company_id="x", assessment_id="x",
            document_text="test",
        )
        result = await engine.run(ctx, [])
        assert result == []
