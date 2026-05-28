"""
Phase 2 master seeder — runs all 33 new regulatory data seeders in sequence.

Usage:
    python scripts/seed_phase2.py                  # Run all seeders
    python scripts/seed_phase2.py --dry-run        # Preview without writing
    python scripts/seed_phase2.py --group fda      # Run FDA group only
    python scripts/seed_phase2.py --skip A3 A13    # Skip specific seeders
    python scripts/seed_phase2.py --only A1 A2     # Run specific seeders only

Groups: fda, mhra, health_canada, ema, who, asia_pacific, other_intl
"""
import argparse
import importlib
import logging
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


@dataclass
class SeederSpec:
    code: str           # e.g. "A1"
    group: str          # e.g. "fda"
    module: str         # importable dotted path
    description: str


SEEDERS: list[SeederSpec] = [
    # ── Group A: FDA ────────────────────────────────────────────────────────────
    SeederSpec("A1",  "fda", "scripts.seeders.fda.seed_fda_crl",
               "FDA Complete Response Letters"),
    SeederSpec("A2",  "fda", "scripts.seeders.fda.seed_fda_closeout",
               "FDA Warning Letter Closeout Letters"),
    SeederSpec("A3",  "fda", "scripts.seeders.fda.seed_fda_dashboards",
               "FDA Data Dashboard XLSX (inspections + compliance)"),
    SeederSpec("A4",  "fda", "scripts.seeders.fda.seed_fda_foia_483_responses",
               "FDA FOIA 483s + Firm Responses"),
    SeederSpec("A5",  "fda", "scripts.seeders.fda.seed_fda_cder_foia",
               "CDER FOIA Electronic Reading Room"),
    SeederSpec("A6",  "fda", "scripts.seeders.fda.seed_fda_drugsatfda",
               "Drugs@FDA Application Data (NDA/ANDA/BLA)"),
    SeederSpec("A7",  "fda", "scripts.seeders.fda.seed_fda_guidance",
               "FDA GMP Guidance Documents"),
    SeederSpec("A8",  "fda", "scripts.seeders.fda.seed_fda_pmr_pmc",
               "FDA Postmarketing Requirements & Commitments"),
    SeederSpec("A9",  "fda", "scripts.seeders.fda.seed_fda_503b",
               "FDA 503B Outsourcing Facilities + Product Reports"),
    SeederSpec("A10", "fda", "scripts.seeders.fda.seed_fda_ndc",
               "FDA NDC Directory"),
    SeederSpec("A11", "fda", "scripts.seeders.fda.seed_fda_otc_monographs",
               "FDA OTC Monographs / Administrative Orders"),
    SeederSpec("A12", "fda", "scripts.seeders.fda.seed_fda_rems",
               "FDA REMS Programs"),
    SeederSpec("A13", "fda", "scripts.seeders.fda.seed_fda_dailymed",
               "DailyMed/SPL Structured Product Labeling"),
    SeederSpec("A14", "fda", "scripts.seeders.fda.seed_fda_caers",
               "CAERS Food Adverse Events"),
    SeederSpec("A15", "fda", "scripts.seeders.fda.seed_fda_mdr_bulk",
               "MDR Bulk Device Reports + ASR"),
    SeederSpec("A16", "fda", "scripts.seeders.fda.seed_fda_cber_alerts",
               "FDA CBER Biologics Safety Alerts"),
    SeederSpec("A17", "fda", "scripts.seeders.fda.seed_fda_bpdr_summaries",
               "FDA BPDR Annual Summaries"),

    # ── Group B: MHRA ───────────────────────────────────────────────────────────
    SeederSpec("B1",  "mhra", "scripts.seeders.mhra.seed_mhra_deficiencies",
               "MHRA GMP Deficiency Spreadsheet"),
    SeederSpec("B2",  "mhra", "scripts.seeders.mhra.seed_mhra_gmdp",
               "MHRA GMDP Database"),
    SeederSpec("B3",  "mhra", "scripts.seeders.mhra.seed_mhra_alerts",
               "MHRA Drug/Device Alerts"),

    # ── Group C: Health Canada ──────────────────────────────────────────────────
    SeederSpec("C1",  "health_canada", "scripts.seeders.health_canada.seed_hc_dhpid",
               "Health Canada Drug & Health Product Inspections Database"),
    SeederSpec("C2",  "health_canada", "scripts.seeders.health_canada.seed_hc_inspection_reports",
               "Health Canada Inspection Reports"),
    SeederSpec("C3",  "health_canada", "scripts.seeders.health_canada.seed_hc_recalls",
               "Health Canada Drug Recalls"),

    # ── Group D: EMA / EU ───────────────────────────────────────────────────────
    SeederSpec("D1",  "ema", "scripts.seeders.ema.seed_ema_epars",
               "EMA European Public Assessment Reports"),
    SeederSpec("D2",  "ema", "scripts.seeders.ema.seed_ema_metrics",
               "EMA Annual Report & GMP Metrics"),
    SeederSpec("D3",  "ema", "scripts.seeders.ema.seed_eu_quality_defects",
               "EU NCA Quality Defects / Rapid Alerts"),
    SeederSpec("D4",  "ema", "scripts.seeders.ema.seed_edqm_cep",
               "EDQM Certificate of Suitability (CEP) Database"),

    # ── Group E: WHO ────────────────────────────────────────────────────────────
    SeederSpec("E1",  "who", "scripts.seeders.who.seed_who_whopirs",
               "WHO Prequalification Inspection Reports (WHOPIRs)"),
    SeederSpec("E2",  "who", "scripts.seeders.who.seed_who_notices",
               "WHO Notices of Concern"),
    SeederSpec("E3",  "who", "scripts.seeders.who.seed_who_alerts",
               "WHO Substandard/Falsified Product Alerts"),

    # ── Group F: Asia-Pacific ───────────────────────────────────────────────────
    SeederSpec("F1",  "asia_pacific", "scripts.seeders.asia_pacific.seed_tga",
               "TGA GMP Clearance Notices + Recalls"),
    SeederSpec("F2",  "asia_pacific", "scripts.seeders.asia_pacific.seed_pmda",
               "PMDA GMP Conformity Assessments"),
    SeederSpec("F3",  "asia_pacific", "scripts.seeders.asia_pacific.seed_swissmedic",
               "Swissmedic GMP Certificates + Alerts"),

    # ── Group G: Other International ────────────────────────────────────────────
    SeederSpec("G1",  "other_intl", "scripts.seeders.other_intl.seed_cdsco",
               "CDSCO (India) Drug Alerts + Inspection Actions"),
    SeederSpec("G2",  "other_intl", "scripts.seeders.other_intl.seed_anvisa",
               "ANVISA (Brazil) GMP Certificates + Alerts"),
]


def run_seeder(spec: SeederSpec, dry_run: bool) -> tuple[bool, float]:
    """Import and run a seeder's main(). Returns (success, elapsed_seconds)."""
    start = time.time()
    try:
        mod = importlib.import_module(spec.module)
        # Patch sys.argv so argparse inside each seeder sees --dry-run
        original_argv = sys.argv[:]
        sys.argv = [spec.module]
        if dry_run:
            sys.argv.append("--dry-run")
        try:
            mod.main()
        finally:
            sys.argv = original_argv
        return True, time.time() - start
    except SystemExit as e:
        if e.code == 0:
            return True, time.time() - start
        log.error(f"  [{spec.code}] Seeder exited with code {e.code}")
        return False, time.time() - start
    except Exception as e:
        log.error(f"  [{spec.code}] FAILED: {e}")
        log.debug(traceback.format_exc())
        return False, time.time() - start


def main():
    parser = argparse.ArgumentParser(
        description="Phase 2 master seeder — run all 33 regulatory data seeders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview records without writing to disk")
    parser.add_argument("--group", metavar="GROUP",
                        help="Only run seeders in this group (fda/mhra/health_canada/ema/who/asia_pacific/other_intl)")
    parser.add_argument("--only", nargs="+", metavar="CODE",
                        help="Only run these seeders by code (e.g. A1 A3 B2)")
    parser.add_argument("--skip", nargs="+", metavar="CODE",
                        help="Skip these seeders by code")
    parser.add_argument("--list", action="store_true",
                        help="List all seeders and exit")
    args = parser.parse_args()

    if args.list:
        print(f"\n{'Code':<6} {'Group':<15} {'Description'}")
        print("-" * 70)
        for s in SEEDERS:
            print(f"{s.code:<6} {s.group:<15} {s.description}")
        print(f"\nTotal: {len(SEEDERS)} seeders")
        return

    # Filter seeders
    to_run = list(SEEDERS)
    if args.group:
        to_run = [s for s in to_run if s.group == args.group]
    if args.only:
        codes = {c.upper() for c in args.only}
        to_run = [s for s in to_run if s.code.upper() in codes]
    if args.skip:
        skip_codes = {c.upper() for c in args.skip}
        to_run = [s for s in to_run if s.code.upper() not in skip_codes]

    if not to_run:
        log.warning("No seeders selected — exiting")
        return

    log.info(f"Phase 2 seeder starting. Running {len(to_run)}/{len(SEEDERS)} seeders.")
    if args.dry_run:
        log.info("DRY-RUN mode — no files will be written.")

    results = []
    total_start = time.time()

    for i, spec in enumerate(to_run, 1):
        log.info(f"\n{'=' * 60}")
        log.info(f"[{i}/{len(to_run)}] {spec.code}: {spec.description}")
        log.info(f"{'=' * 60}")
        success, elapsed = run_seeder(spec, args.dry_run)
        results.append((spec, success, elapsed))
        if success:
            log.info(f"  [{spec.code}] OK in {elapsed:.1f}s")
        else:
            log.error(f"  [{spec.code}] FAILED after {elapsed:.1f}s")

    # Summary
    total_elapsed = time.time() - total_start
    successes = [r for r in results if r[1]]
    failures = [r for r in results if not r[1]]

    log.info(f"\n{'=' * 60}")
    log.info(f"PHASE 2 COMPLETE")
    log.info(f"  Total:   {len(results)} seeders in {total_elapsed:.0f}s")
    log.info(f"  Success: {len(successes)}")
    log.info(f"  Failed:  {len(failures)}")

    if failures:
        log.error("\nFailed seeders:")
        for spec, _, elapsed in failures:
            log.error(f"  {spec.code}: {spec.description} (after {elapsed:.1f}s)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
