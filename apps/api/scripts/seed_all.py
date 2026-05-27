"""
Master Enforcement Intelligence Pipeline Runner
===============================================
Runs all Phase-0 seeders in the recommended sequence with progress reporting.
Pass --dry-run to preview without writing any files.

Usage:
    cd apps/api
    python scripts/seed_all.py
    python scripts/seed_all.py --dry-run
    python scripts/seed_all.py --only enforcement,ecfr
    python scripts/seed_all.py --skip who_pq,eu_gmp
"""
import argparse
import asyncio
import importlib
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_all")

RAG_INDEX = Path(__file__).parent.parent / "rag_index"

# Ordered list of (seeder_name, module_name, description)
# Pure-API / regulatory text first (less likely to fail), scrapers second
SEEDERS: list[tuple[str, str, str]] = [
    ("enforcement", "seed_enforcement",    "openFDA drug/device/food enforcement + FDA Warning Letters + EMA"),
    ("ecfr",        "seed_ecfr",           "21 CFR Title 21 live regulatory text (replaces static corpus)"),
    ("ich",         "seed_ich",            "ICH guidelines Q1-Q14, E6(R3), S-series (PDF text)"),
    ("eu_gmp",      "seed_eu_gmp",         "EudraLex Volume 4 main chapters + Annexes 1–19 (PDF text)"),
    ("483s",        "seed_483s",           "FDA Form 483 inspection observations (EFTS + PDF extraction)"),
    ("icdb",        "seed_icdb",           "FDA Inspection Classification Database (NAI/VAI/OAI records)"),
    ("consent",     "seed_consent_decrees","FDA consent decrees index + detail pages"),
    ("import",      "seed_import_alerts",  "FDA import alerts (DWPE + automatic detention)"),
    ("who_pq",      "seed_who_pq",         "WHO Prequalification inspection outcomes + notices"),
]


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _rag_summary() -> dict[str, int]:
    return {
        "observations.jsonl":      _count_lines(RAG_INDEX / "observations.jsonl"),
        "observations_483.jsonl":  _count_lines(RAG_INDEX / "observations_483.jsonl"),
        "regulatory_corpus.jsonl": _count_lines(RAG_INDEX / "regulatory_corpus.jsonl"),
        "inspections.jsonl":       _count_lines(RAG_INDEX / "inspections.jsonl"),
        "consent_decrees.jsonl":   _count_lines(RAG_INDEX / "consent_decrees.jsonl"),
        "import_alerts.jsonl":     _count_lines(RAG_INDEX / "import_alerts.jsonl"),
        "ich_guidelines.jsonl":    _count_lines(RAG_INDEX / "ich_guidelines.jsonl"),
        "eu_gmp.jsonl":            _count_lines(RAG_INDEX / "eu_gmp.jsonl"),
        "who_pq.jsonl":            _count_lines(RAG_INDEX / "who_pq.jsonl"),
        "failure_modes.jsonl":     _count_lines(RAG_INDEX / "failure_modes.jsonl"),
    }


async def run_seeder(name: str, module_name: str, dry_run: bool) -> tuple[bool, float]:
    """Import and run a seeder's main() coroutine. Returns (success, elapsed_sec)."""
    script_dir = Path(__file__).parent
    module_path = script_dir / f"{module_name}.py"

    if not module_path.exists():
        log.error(f"  [{name}] Module not found: {module_path}")
        return False, 0.0

    # Dynamically import without polluting sys.argv
    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Inject --dry-run via sys.argv override for argparse inside each seeder
    original_argv = sys.argv[:]
    sys.argv = [module_path.name]
    if dry_run:
        sys.argv.append("--dry-run")

    t0 = time.monotonic()
    success = True
    try:
        if hasattr(mod, "main"):
            if asyncio.iscoroutinefunction(mod.main):
                await mod.main()
            else:
                mod.main()
        else:
            log.warning(f"  [{name}] No main() found in {module_name}")
    except SystemExit:
        pass  # argparse calls sys.exit(0) on --help; ignore
    except Exception as e:
        log.error(f"  [{name}] Seeder raised exception: {e}", exc_info=True)
        success = False
    finally:
        sys.argv = original_argv

    return success, time.monotonic() - t0


async def main():
    parser = argparse.ArgumentParser(description="Run all Clyira enforcement intelligence seeders")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--only", default="", help="Comma-separated seeder names to run exclusively")
    parser.add_argument("--skip", default="", help="Comma-separated seeder names to skip")
    args = parser.parse_args()

    only = set(s.strip() for s in args.only.split(",") if s.strip())
    skip = set(s.strip() for s in args.skip.split(",") if s.strip())

    seeders_to_run = [
        (name, mod, desc) for name, mod, desc in SEEDERS
        if (not only or name in only) and name not in skip
    ]

    log.info("=" * 60)
    log.info("Clyira Phase-0 Enforcement Intelligence Pipeline")
    log.info(f"Seeders: {len(seeders_to_run)}   dry_run={args.dry_run}")
    log.info("=" * 60)

    before = _rag_summary()

    results: list[tuple[str, bool, float]] = []
    for i, (name, module_name, desc) in enumerate(seeders_to_run, 1):
        log.info(f"\n[{i}/{len(seeders_to_run)}] {name}: {desc}")
        success, elapsed = await run_seeder(name, module_name, args.dry_run)
        results.append((name, success, elapsed))
        status = "OK" if success else "FAILED"
        log.info(f"  → {status} in {elapsed:.1f}s")

    after = _rag_summary()

    log.info("\n" + "=" * 60)
    log.info("Pipeline complete — RAG index summary")
    log.info("=" * 60)
    total_before = total_after = 0
    for fname, before_count in before.items():
        after_count = after.get(fname, 0)
        delta = after_count - before_count
        total_before += before_count
        total_after += after_count
        sign = f"+{delta}" if delta >= 0 else str(delta)
        log.info(f"  {fname:<30} {before_count:>7} → {after_count:>7}  ({sign})")

    log.info("-" * 60)
    log.info(f"  {'TOTAL':<30} {total_before:>7} → {total_after:>7}  (+{total_after - total_before})")

    failed = [n for n, ok, _ in results if not ok]
    if failed:
        log.warning(f"\nFailed seeders: {failed}")
    else:
        log.info("\nAll seeders completed successfully.")

    total_time = sum(e for _, _, e in results)
    log.info(f"Total wall time: {total_time:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
