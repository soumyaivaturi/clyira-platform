"""
International Enforcement Engine — BM25 search over non-FDA enforcement actions.

Loads all available international enforcement JSONL files from rag_index:
  - who_pq*.jsonl          (WHO Prequalification / enforcement notices)
  - consent_decrees*.jsonl (FDA Consent Decrees — domestic but distinct from WLs)
  - mhra*.jsonl            (UK MHRA enforcement actions)
  - health_canada*.jsonl   (Health Canada compliance actions)
  - tga*.jsonl             (Australian TGA)
  - cdsco*.jsonl           (India CDSCO)
  - eu_alerts*.jsonl       (EMA safety and enforcement alerts)
  - doj*.jsonl             (DOJ pharmaceutical enforcement)

All files are optional — missing files are skipped with a warning.
Results are tagged with source_agency so callers can weight by authority.

Used by enforcement_engine.py to extend L9 pattern matching beyond FDA WLs.
Singleton, lazy-loaded, thread-safe.
"""
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_INDEX_DIR = Path(__file__).parent.parent.parent / "rag_index"
_ENV_INDEX = os.getenv("RAG_INDEX_PATH")
_LOCAL_INDEX_DIR = Path.home() / "Documents" / "Clyira-Corpus" / "rag_index"

# (glob_pattern, source_agency_label, weight_vs_fda)
# Weight < 1.0 means results will be scored lower relative to FDA actions in combined ranking
_SOURCE_CONFIGS = [
    # FDA-adjacent
    ("consent_decrees*.jsonl",          "FDA/DOJ",        1.0),
    ("doj*.jsonl",                      "DOJ",            0.90),
    # MHRA (UK)
    ("mhra*.jsonl",                     "MHRA",           0.85),
    ("mhra_gmdp*.jsonl",                "MHRA",           0.85),
    ("mhra_deficiencies*.jsonl",        "MHRA",           0.85),
    ("mhra_alerts*.jsonl",              "MHRA",           0.85),
    # Health Canada
    ("health_canada*.jsonl",            "Health Canada",  0.80),
    ("hc_dhpid*.jsonl",                 "Health Canada",  0.80),
    ("hc_inspection*.jsonl",            "Health Canada",  0.80),
    ("hc_recalls*.jsonl",               "Health Canada",  0.80),
    # EMA / EU
    ("eu_alerts*.jsonl",                "EMA",            0.85),
    ("ema_epars*.jsonl",                "EMA",            0.85),
    ("ema_metrics*.jsonl",              "EMA",            0.80),
    ("eu_quality_defects*.jsonl",       "EMA",            0.85),
    ("edqm_cep*.jsonl",                 "EDQM",           0.80),
    # WHO
    ("who_pq*.jsonl",                   "WHO",            0.70),
    ("who_whopirs*.jsonl",              "WHO",            0.70),
    ("who_notices*.jsonl",              "WHO",            0.70),
    ("who_alerts*.jsonl",               "WHO",            0.70),
    # TGA (Australia)
    ("tga*.jsonl",                      "TGA",            0.75),
    ("tga_gmp_notices*.jsonl",          "TGA",            0.75),
    ("tga_recalls*.jsonl",              "TGA",            0.75),
    # PMDA (Japan)
    ("pmda*.jsonl",                     "PMDA",           0.70),
    # Swissmedic
    ("swissmedic*.jsonl",               "Swissmedic",     0.70),
    # CDSCO (India)
    ("cdsco*.jsonl",                    "CDSCO",          0.60),
    # ANVISA (Brazil)
    ("anvisa*.jsonl",                   "ANVISA",         0.60),
]

_lock = threading.Lock()
_bm25 = None
_corpus: list[dict] = []      # enriched with source_agency + agency_weight


def _resolve_index_dir() -> Path:
    if _ENV_INDEX:
        p = Path(_ENV_INDEX)
        return p.parent if p.is_file() else p
    if _REPO_INDEX_DIR.exists():
        return _REPO_INDEX_DIR
    return _LOCAL_INDEX_DIR


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text_clean = re.sub(r'[^a-z0-9.\s]', ' ', text)
    return text_clean.split()


def _doc_text(doc: dict) -> str:
    return doc.get('text', doc.get('summary', doc.get('description', doc.get('content', ''))))


def _load_index() -> bool:
    global _bm25, _corpus
    index_dir = _resolve_index_dir()
    if not index_dir.exists():
        logger.warning(f"International enforcement index dir not found at {index_dir}")
        return False
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank-bm25 not installed — international enforcement search disabled")
        return False

    combined: list[dict] = []
    for pattern, agency, weight in _SOURCE_CONFIGS:
        files = sorted(index_dir.glob(pattern))
        if not files:
            logger.debug(f"No files matching {pattern} — skipping {agency}")
            continue
        for path in files:
            count_before = len(combined)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        doc = json.loads(line)
                        doc['source_agency'] = doc.get('source_agency', agency)
                        doc['agency_weight'] = weight
                        combined.append(doc)
            except Exception as e:
                logger.warning(f"Failed to load {path.name}: {e}")
                continue
            logger.info(f"  International enforcement: loaded {len(combined) - count_before} records from {path.name} [{agency}]")

    if not combined:
        logger.warning("No international enforcement files found — international matching disabled")
        return False

    _corpus = combined
    tokenized = [_tokenize(_doc_text(doc)) for doc in _corpus]
    _bm25 = BM25Okapi(tokenized)
    logger.info(f"International enforcement BM25 ready: {len(_corpus)} records")
    return True


def _ensure_loaded() -> bool:
    global _bm25
    if _bm25 is not None:
        return True
    with _lock:
        if _bm25 is None:
            return _load_index()
    return _bm25 is not None


def search(
    query: str,
    n_results: int = 3,
    agency_filter: Optional[str] = None,
) -> list[dict]:
    """
    BM25 search over international enforcement actions.

    Returns up to n_results dicts with keys:
        text, company, year, source_agency, agency_weight, cfr_citations, score

    Results are pre-filtered to score >= 0.5 (same threshold as rag_engine).
    Returns [] if corpus unavailable.
    """
    if not _ensure_loaded():
        return []

    query_tokens = _tokenize(query)
    scores = _bm25.get_scores(query_tokens)
    candidates = list(enumerate(scores))

    if agency_filter:
        candidates = [
            (i, s) for i, s in candidates
            if agency_filter.lower() in _corpus[i].get('source_agency', '').lower()
        ] or candidates

    top = sorted(candidates, key=lambda x: x[1], reverse=True)[:n_results]

    results = []
    for idx, score in top:
        if score < 0.5:
            continue
        doc = _corpus[idx]
        text = _doc_text(doc)
        results.append({
            'text': text[:1200],
            'company': doc.get('company', doc.get('firm_name', doc.get('subject', ''))),
            'year': doc.get('year', doc.get('date', '')[:4] if doc.get('date') else ''),
            'source_agency': doc.get('source_agency', ''),
            'agency_weight': doc.get('agency_weight', 0.7),
            'source_type': doc.get('source_type', 'international_enforcement'),
            'cfr_citations': doc.get('cfr_citations', doc.get('regulatory_citations', [])),
            'score': round(float(score), 2),
        })
    return results


def get_agencies_with_data() -> list[str]:
    """Return list of agency names for which data is loaded."""
    _ensure_loaded()
    if not _corpus:
        return []
    from collections import Counter
    counts: Counter = Counter(doc.get('source_agency', 'unknown') for doc in _corpus)
    return [agency for agency, _ in counts.most_common()]


def format_international_excerpt(results: list[dict]) -> str:
    """Format international enforcement results as context string."""
    if not results:
        return ""
    parts = []
    for r in results:
        agency = r.get('source_agency', 'International')
        company = r.get('company', '')
        year = r.get('year', '')
        header = f"[{agency} — {company} {year}]".strip()
        parts.append(f"{header}\n{r['text'][:600]}")
    return "\n\n---\n\n".join(parts)
