"""
Regulatory Corpus Engine — BM25 search over eCFR, ICH guidelines, EU GMP, and PIC/S.

Loads all regulatory JSONL files from the rag_index directory:
  - regulatory_corpus*.jsonl  (eCFR text, seeded by seed_ecfr.py)
  - ich_guidelines*.jsonl     (ICH Q/E/S/M guidelines, seeded by seed_ich.py)
  - eu_gmp*.jsonl             (EudraLex Volume 4, seeded by seed_eu_gmp.py)
  - pics_guidelines*.jsonl    (PIC/S guides, if present)

Powers L8 checks: provides actual regulation and guideline text as context
for LLM regulatory reporting assessments.

Singleton, lazy-loaded, thread-safe. Gracefully skips missing files.
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

_GLOB_PATTERNS = [
    "regulatory_corpus*.jsonl",
    "ich_guidelines*.jsonl",
    "eu_gmp*.jsonl",
    "pics_guidelines*.jsonl",
    # Phase-2: FDA guidance documents
    "fda_guidance_documents*.jsonl",
    # Phase-2: OTC monographs, REMS, PMR/PMC (regulatory requirements)
    "fda_otc_monographs*.jsonl",
    "fda_rems*.jsonl",
    "fda_pmr_pmc*.jsonl",
    # Phase-2: EMA EPARs and EDQM
    "ema_epars*.jsonl",
    "edqm_cep*.jsonl",
    # Phase-2: BPDR annual summaries (CBER regulatory context)
    "fda_bpdr_summaries*.jsonl",
]

# Map glob prefix → regulatory body label
_SOURCE_LABELS = {
    "regulatory_corpus": "FDA/eCFR",
    "ich_guidelines": "ICH",
    "eu_gmp": "EMA/EU GMP",
    "pics_guidelines": "PIC/S",
    "fda_guidance_documents": "FDA Guidance",
    "fda_otc_monographs": "FDA/OTC",
    "fda_rems": "FDA/REMS",
    "fda_pmr_pmc": "FDA/PMR-PMC",
    "ema_epars": "EMA/EPAR",
    "edqm_cep": "EDQM",
    "fda_bpdr_summaries": "FDA/CBER",
}

_lock = threading.Lock()
_bm25 = None
_corpus: list[dict] = []


def _resolve_index_dir() -> Path:
    if _ENV_INDEX:
        p = Path(_ENV_INDEX)
        return p.parent if p.is_file() else p
    if _REPO_INDEX_DIR.exists():
        return _REPO_INDEX_DIR
    return _LOCAL_INDEX_DIR


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    cfr_tokens = re.findall(r'21\s*cfr\s*[\d.]+', text)
    text_clean = re.sub(r'[^a-z0-9.\s]', ' ', text)
    tokens = text_clean.split()
    for c in cfr_tokens:
        normalized = re.sub(r'\s+', '', c).lower()
        if normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _doc_text(doc: dict) -> str:
    return doc.get('text', doc.get('content', doc.get('section_text', '')))


def _load_index() -> bool:
    global _bm25, _corpus
    index_dir = _resolve_index_dir()
    if not index_dir.exists():
        logger.warning(f"Regulatory corpus index dir not found at {index_dir} — regulatory search disabled")
        return False
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        logger.warning("rank-bm25 not installed — regulatory corpus search disabled")
        return False

    combined: list[dict] = []
    for pattern in _GLOB_PATTERNS:
        prefix = pattern.split("*")[0]
        label = _SOURCE_LABELS.get(prefix, prefix.replace("_", " ").title())
        for path in sorted(index_dir.glob(pattern)):
            count_before = len(combined)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        doc = json.loads(line)
                        # Normalize source field
                        if 'source_body' not in doc:
                            doc['source_body'] = label
                        combined.append(doc)
            except Exception as e:
                logger.warning(f"Failed to load {path.name}: {e}")
                continue
            loaded = len(combined) - count_before
            logger.info(f"  Regulatory corpus: loaded {loaded} records from {path.name} [{label}]")

    if not combined:
        logger.warning("No regulatory corpus files found — regulatory search disabled")
        return False

    _corpus = combined
    tokenized = [_tokenize(_doc_text(doc)) for doc in _corpus]
    _bm25 = BM25Okapi(tokenized)
    logger.info(f"Regulatory corpus BM25 ready: {len(_corpus)} records across {len(_GLOB_PATTERNS)} source types")
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
    cfr_filter: Optional[str] = None,
    source_body_filter: Optional[str] = None,
) -> list[dict]:
    """
    BM25 search over the regulatory corpus (eCFR + ICH + EU GMP + PIC/S).

    Returns up to n_results dicts with keys:
        text, cfr_citation, citation_reference, source_body, part, section, score

    Returns [] if corpus is unavailable (graceful degradation).
    """
    if not _ensure_loaded():
        return []

    query_tokens = _tokenize(query)
    scores = _bm25.get_scores(query_tokens)
    candidates = list(enumerate(scores))

    if cfr_filter:
        cfr_norm = cfr_filter.lower().replace(' ', '')
        filtered = [
            (i, s) for i, s in candidates
            if cfr_norm in (
                _corpus[i].get('cfr_citation', '') + ' ' +
                _corpus[i].get('citation_reference', '')
            ).lower().replace(' ', '')
        ]
        candidates = filtered or candidates

    if source_body_filter:
        candidates = [
            (i, s) for i, s in candidates
            if source_body_filter.lower() in _corpus[i].get('source_body', '').lower()
        ] or candidates

    top = sorted(candidates, key=lambda x: x[1], reverse=True)[:n_results]

    results = []
    for idx, score in top:
        if score < 0.5:
            continue
        doc = _corpus[idx]
        text = _doc_text(doc)
        results.append({
            'text': text[:2000],
            'cfr_citation': doc.get('cfr_citation', doc.get('citation_reference', '')),
            'citation_reference': doc.get('citation_reference', doc.get('cfr_citation', '')),
            'source_body': doc.get('source_body', ''),
            'part': doc.get('part', ''),
            'section': doc.get('section', ''),
            'title': doc.get('title', doc.get('section_title', '')),
            'score': round(float(score), 2),
        })
    return results


def get_regulation_text(cfr_citation: str) -> Optional[str]:
    """
    Retrieve the full text of a specific CFR section.
    Returns None if not found.
    """
    results = search(cfr_citation, n_results=1, cfr_filter=cfr_citation)
    return results[0]['text'] if results else None


def format_regulatory_context(results: list[dict]) -> str:
    """Format corpus search results as context string for LLM prompts."""
    if not results:
        return ""
    parts = []
    for r in results:
        citation = r.get('cfr_citation') or r.get('citation_reference', '')
        body = r.get('source_body', '')
        header = f"[{body} — {citation}]" if citation else f"[{body}]"
        parts.append(f"{header}\n{r['text'][:800]}")
    return "\n\n---\n\n".join(parts)
