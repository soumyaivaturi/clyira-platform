"""
RAG Engine — BM25 search over FDA Warning Letter + Form 483 observations.
Lazy-loaded once per process at first query; thread-safe singleton.

Loads all observations*.jsonl files from the rag_index directory so that
Warning Letter observations (observations.jsonl) and Form 483 observations
(observations_483.jsonl) are searched together.

Path resolution order for the index directory:
  1. RAG_INDEX_PATH env var (directory or single-file path)
  2. apps/api/rag_index/ (bundled in repo)
  3. ~/Documents/Clyira-Corpus/rag_index/ (local dev)
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


def _resolve_index_dir() -> Path:
    if _ENV_INDEX:
        p = Path(_ENV_INDEX)
        return p.parent if p.is_file() else p
    if _REPO_INDEX_DIR.exists():
        return _REPO_INDEX_DIR
    return _LOCAL_INDEX_DIR


INDEX_DIR = _resolve_index_dir()

_lock = threading.Lock()
_bm25 = None
_corpus: list[dict] = []
_cfr_freq: dict[str, int] = {}   # normalized CFR key → observation count


# ──────────────────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Tokenize text, keeping CFR citation strings as single tokens."""
    text = text.lower()
    cfr_tokens = re.findall(r'21\s*cfr\s*[\d.]+', text)
    text_clean = re.sub(r'[^a-z0-9.\s]', ' ', text)
    tokens = text_clean.split()
    for c in cfr_tokens:
        normalized = re.sub(r'\s+', '', c).lower()
        if normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _normalize_cfr(citation: str) -> str:
    """Normalize a CFR citation to a lookup key, e.g. '21 CFR 211.192(a)' → '21cfr211.192'."""
    m = re.search(r'21\s*cfr\s*([\d.]+)', citation, re.IGNORECASE)
    if m:
        return f"21cfr{m.group(1).rstrip('.')}"
    return citation.lower().replace(' ', '')


def _build_cfr_freq(corpus: list[dict]) -> dict[str, int]:
    from collections import Counter
    counts: Counter = Counter()
    for doc in corpus:
        for c in doc.get('cfr_citations', []):
            counts[_normalize_cfr(c)] += 1
    return dict(counts)


def _load_index() -> bool:
    global _bm25, _corpus, _cfr_freq
    if not INDEX_DIR.exists():
        logger.warning(f"RAG index directory not found at {INDEX_DIR} — enforcement matching disabled")
        return False
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank-bm25 not installed — enforcement matching disabled")
        return False

    # Load all observations*.jsonl files so WL + 483 observations are searched together
    obs_files = sorted(INDEX_DIR.glob("observations*.jsonl"))
    if not obs_files:
        logger.warning(f"No observations*.jsonl found in {INDEX_DIR} — enforcement matching disabled")
        return False

    combined: list[dict] = []
    for path in obs_files:
        count_before = len(combined)
        with open(path, 'r', encoding='utf-8') as f:
            combined.extend(json.loads(line) for line in f if line.strip())
        logger.info(f"  Loaded {len(combined) - count_before} records from {path.name}")

    _corpus = combined
    tokenized = [_tokenize(doc.get('text', '')) for doc in _corpus]
    _bm25 = BM25Okapi(tokenized)
    _cfr_freq = _build_cfr_freq(_corpus)
    logger.info(f"BM25 index ready: {len(_corpus)} observations across {len(obs_files)} files, {len(_cfr_freq)} unique CFR sections")
    return True


def _ensure_loaded() -> bool:
    global _bm25
    if _bm25 is not None:
        return True
    with _lock:
        if _bm25 is None:
            return _load_index()
    return _bm25 is not None


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def search(
    query: str,
    n_results: int = 2,
    cfr_filter: Optional[str] = None,
) -> list[dict]:
    """
    BM25 search over FDA Warning Letter observations.

    Returns up to n_results dicts with keys:
        text, company, year, office, source_url, cfr_citations, score

    Returns [] if the index is unavailable (graceful degradation).
    """
    if not _ensure_loaded():
        return []

    query_tokens = _tokenize(query)
    scores = _bm25.get_scores(query_tokens)
    candidates = list(enumerate(scores))

    if cfr_filter:
        cfr_norm = _normalize_cfr(cfr_filter)
        filtered = [
            (i, s) for i, s in candidates
            if any(_normalize_cfr(c) == cfr_norm for c in _corpus[i].get('cfr_citations', []))
        ]
        candidates = filtered or candidates  # fall back to all if filter yields nothing

    top = sorted(candidates, key=lambda x: x[1], reverse=True)[:n_results]

    results = []
    for idx, score in top:
        if score < 0.5:
            continue
        doc = _corpus[idx]
        results.append({
            'text': doc['text'][:1200],
            'company': doc['company'],
            'year': doc['year'],
            'office': doc['office'],
            'source_url': doc['source_url'],
            'cfr_citations': doc['cfr_citations'],
            'score': round(float(score), 2),
        })
    return results


def get_cfr_observation_count(citation: str) -> int:
    """
    Return how many Warning Letter observations cite this CFR section.
    Used for L9 severity elevation thresholds.
    """
    if not _ensure_loaded():
        return 0
    return _cfr_freq.get(_normalize_cfr(citation), 0)


def format_enforcement_excerpt(precedents: list[dict]) -> str:
    """
    Format BM25 results into a compact enforcement_context string attached to findings.
    """
    if not precedents:
        return ""
    parts = []
    for p in precedents:
        header = f"[{p['company']}, {p['office']} Warning Letter {p['year']}]"
        parts.append(f"{header}\n{p['text'][:600]}")
    return "\n\n---\n\n".join(parts)
