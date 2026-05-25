"""Record integrity — SHA-256 hashing for tamper-evident records (21 CFR Part 11 §11.10(e))."""
import hashlib
import json
from typing import Any


def compute_hash(data: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of a JSON-serialized dict (keys sorted for determinism)."""
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
