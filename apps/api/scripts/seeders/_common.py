"""
Shared utilities for all Phase-2 seeders.
"""
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).parent.parent
API_DIR = SCRIPTS_DIR.parent
RAG_INDEX = API_DIR / "rag_index"


def get_rag_index() -> Path:
    RAG_INDEX.mkdir(exist_ok=True)
    return RAG_INDEX


# ── HTTP helpers ──────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ClyiraBot/1.0; +https://clyira.ai; "
        "regulatory-intelligence-research)"
    )
}


def get(url: str, delay: float = 0.4, timeout: float = 30.0, **kwargs) -> Optional[httpx.Response]:
    """GET with retry, rate-limit delay, and graceful error handling."""
    time.sleep(delay)
    log = logging.getLogger("seeder")
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True, **kwargs)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                wait = 10 * (attempt + 1)
                log.warning(f"Rate limited ({r.status_code}) on {url} — waiting {wait}s")
                time.sleep(wait)
            elif r.status_code in (404, 410):
                log.debug(f"Not found ({r.status_code}): {url}")
                return None
            else:
                log.warning(f"HTTP {r.status_code} for {url}")
                return None
        except Exception as e:
            log.warning(f"Request error (attempt {attempt+1}/3) for {url}: {e}")
            time.sleep(3)
    return None


# ── JSONL helpers ─────────────────────────────────────────────────────────────
def load_existing_keys(path: Path, key_field: str) -> set:
    if not path.exists():
        return set()
    keys = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    keys.add(json.loads(line).get(key_field, ""))
                except Exception:
                    pass
    return keys


def load_existing_compound_keys(path: Path, fields: list) -> set:
    if not path.exists():
        return set()
    keys = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    keys.add(tuple(rec.get(f, "") for f in fields))
                except Exception:
                    pass
    return keys


def append_records(path: Path, records: list, dry_run: bool, log) -> int:
    if dry_run:
        for r in records[:3]:
            log.info(f"  [DRY-RUN] {json.dumps(r)[:200]}")
        return len(records)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


# ── PDF helpers ───────────────────────────────────────────────────────────────
def pdf_to_text(content: bytes, max_pages: int = 50) -> str:
    """Extract text from PDF bytes using pdfplumber with PyPDF2 fallback."""
    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = pdf.pages[:max_pages]
            return "\n".join(p.extract_text() or "" for p in pages)
    except Exception:
        pass
    try:
        import PyPDF2
        import io
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        texts = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


# ── ID generation ─────────────────────────────────────────────────────────────
def make_id(prefix: str, *parts) -> str:
    import hashlib
    key = "|".join(str(p) for p in parts)
    return f"{prefix}-{hashlib.md5(key.encode()).hexdigest()[:12]}"
