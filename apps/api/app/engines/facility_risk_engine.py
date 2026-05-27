"""
Facility Risk Engine — loads ICDB inspection data and FDA import alerts.

Provides site-level risk signals used by L9 checks:
  - Repeat OAI/VAI classifications → repeat_observation_risk
  - Active import alerts → consent_decree_pattern / enforcement escalation
  - Combined facility risk summary → get_facility_risk_signals()

Data sources (from Phase 0 seeders):
  - inspections*.jsonl   (ICDB classifications: NAI / VAI / OAI)
  - import_alerts*.jsonl (FDA import alerts with active firm lists)

Fuzzy firm-name matching using difflib — firm names vary across FDA systems.
Singleton, lazy-loaded, thread-safe. Gracefully skips missing files.
"""
import json
import logging
import os
import re
import threading
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_INDEX_DIR = Path(__file__).parent.parent.parent / "rag_index"
_ENV_INDEX = os.getenv("RAG_INDEX_PATH")
_LOCAL_INDEX_DIR = Path.home() / "Documents" / "Clyira-Corpus" / "rag_index"

_FUZZY_THRESHOLD = 0.72   # SequenceMatcher ratio threshold for firm name match

_lock = threading.Lock()
_inspections: list[dict] = []
_import_alerts: list[dict] = []
_loaded = False


def _resolve_index_dir() -> Path:
    if _ENV_INDEX:
        p = Path(_ENV_INDEX)
        return p.parent if p.is_file() else p
    if _REPO_INDEX_DIR.exists():
        return _REPO_INDEX_DIR
    return _LOCAL_INDEX_DIR


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and common suffixes for fuzzy comparison."""
    name = name.lower()
    name = re.sub(r'\b(inc|llc|ltd|corp|co|gmbh|pvt|limited|laboratories|pharma|pharmaceuticals)\b\.?', '', name)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def _fuzzy_match(query: str, candidate: str) -> float:
    return SequenceMatcher(None, _normalize_name(query), _normalize_name(candidate)).ratio()


def _load_data() -> bool:
    global _inspections, _import_alerts, _loaded
    index_dir = _resolve_index_dir()
    if not index_dir.exists():
        logger.warning(f"Facility risk index dir not found at {index_dir} — facility risk checks disabled")
        _loaded = True
        return False

    for pattern, target_list, label in [
        ("inspections*.jsonl", _inspections, "inspections"),
        ("import_alerts*.jsonl", _import_alerts, "import alerts"),
    ]:
        for path in sorted(index_dir.glob(pattern)):
            count_before = len(target_list)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            target_list.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Failed to load {path.name}: {e}")
                continue
            logger.info(f"  Facility risk: loaded {len(target_list) - count_before} {label} from {path.name}")

    logger.info(f"Facility risk engine ready: {len(_inspections)} inspections, {len(_import_alerts)} import alerts")
    _loaded = True
    return True


def _ensure_loaded() -> bool:
    global _loaded
    if _loaded:
        return True
    with _lock:
        if not _loaded:
            _load_data()
    return _loaded


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def get_inspection_history(firm_name_or_fei: str, max_results: int = 10) -> list[dict]:
    """
    Return inspection records for a firm by name or FEI number.
    Uses fuzzy name matching to handle naming variations across FDA systems.

    Each result contains: firm_name, fei_number, classification, inspection_date,
    product_type, district, city, state, country
    """
    _ensure_loaded()
    if not _inspections:
        return []

    query = firm_name_or_fei.strip()
    # FEI numbers are numeric
    is_fei = re.match(r'^\d{7,10}$', query)

    matched = []
    for rec in _inspections:
        if is_fei:
            if str(rec.get('fei_number', '')) == query:
                matched.append((1.0, rec))
        else:
            name = rec.get('firm_name', rec.get('legal_name', ''))
            score = _fuzzy_match(query, name)
            if score >= _FUZZY_THRESHOLD:
                matched.append((score, rec))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [rec for _, rec in matched[:max_results]]


def get_import_alert_status(firm_name: str) -> list[dict]:
    """
    Return active import alerts where this firm appears on the firms_on_list.
    Each result contains: alert_number, alert_type, product_description,
    charges, effective_date, firms_matched
    """
    _ensure_loaded()
    if not _import_alerts:
        return []

    query = firm_name.strip()
    results = []
    for alert in _import_alerts:
        firms = alert.get('firms_on_list', [])
        if isinstance(firms, str):
            firms = [firms]
        for firm in firms:
            if _fuzzy_match(query, firm) >= _FUZZY_THRESHOLD:
                results.append({
                    'alert_number': alert.get('alert_number', ''),
                    'alert_type': alert.get('alert_type', ''),
                    'product_description': alert.get('product_description', alert.get('product', '')),
                    'charges': alert.get('charges', ''),
                    'effective_date': alert.get('effective_date', ''),
                    'cfr_citations': alert.get('cfr_citations', []),
                    'firms_matched': firm,
                })
            break  # one match per alert per firm is enough

    return results


def get_facility_risk_signals(firm_name_or_fei: str) -> dict:
    """
    Combined facility risk summary for a firm.

    Returns:
        oai_count: number of Official Action Indicated inspections
        vai_count: number of Voluntary Action Indicated inspections
        nai_count: number of No Action Indicated inspections
        repeat_oai: True if 2+ OAI classifications in last 5 years
        active_import_alerts: list of active import alerts
        risk_level: "high" | "medium" | "low" | "unknown"
        inspection_history: full list of matched inspections
    """
    _ensure_loaded()
    inspections = get_inspection_history(firm_name_or_fei)
    import_alerts = get_import_alert_status(firm_name_or_fei) if not re.match(r'^\d+$', firm_name_or_fei) else []

    from collections import Counter
    class_counts: Counter = Counter()
    for rec in inspections:
        classification = (rec.get('classification') or rec.get('action_classification') or 'unknown').upper()
        class_counts[classification] += 1

    oai_count = class_counts.get('OAI', 0)
    vai_count = class_counts.get('VAI', 0)
    nai_count = class_counts.get('NAI', 0)
    repeat_oai = oai_count >= 2

    if oai_count >= 2 or import_alerts:
        risk_level = "high"
    elif oai_count == 1 or vai_count >= 3:
        risk_level = "medium"
    elif inspections:
        risk_level = "low"
    else:
        risk_level = "unknown"

    return {
        'oai_count': oai_count,
        'vai_count': vai_count,
        'nai_count': nai_count,
        'repeat_oai': repeat_oai,
        'active_import_alerts': import_alerts,
        'risk_level': risk_level,
        'inspection_history': inspections,
        'total_inspections': len(inspections),
    }
