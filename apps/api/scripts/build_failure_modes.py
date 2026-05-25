"""
Failure Mode Library Builder
============================
Clusters observations.jsonl into named failure patterns and writes
failure_modes.jsonl to apps/api/rag_index/.

Run from apps/api/:
    python scripts/build_failure_modes.py

Output: apps/api/rag_index/failure_modes.jsonl
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
RAG_INDEX = SCRIPT_DIR.parent / "rag_index"
OBS_PATH = RAG_INDEX / "observations.jsonl"
OUTPUT_PATH = RAG_INDEX / "failure_modes.jsonl"

# ── Failure Mode Definitions ──────────────────────────────────────────────────
# Each mode: id, name, description, keywords (for matching), primary_cfr,
# severity_range, doc_categories, root_cause_categories, evidence_indicators

FAILURE_MODE_DEFS = [
    {
        "id": "FM-001",
        "name": "OOS Investigation Failure",
        "description": "Failure to adequately investigate out-of-specification laboratory results, including inadequate root cause analysis, failure to extend investigation to retained samples, or premature invalidation of results.",
        "keywords": ["out-of-specification", "out of specification", "oos", "failed test result", "laboratory investigation", "invalidat"],
        "primary_cfr": ["21 CFR 211.192", "21 CFR 211.165", "21 CFR 211.160"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["ATM", "LIR", "Deviation", "CAPA"],
        "root_cause_categories": ["inadequate_investigation", "data_integrity", "analytical_method_failure"],
        "evidence_indicators": [
            "OOS results not thoroughly investigated",
            "Root cause not identified",
            "Retesting without adequate justification",
            "Failure to extend investigation to production batch",
            "Assignable cause not documented",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4"],
    },
    {
        "id": "FM-002",
        "name": "CAPA System Deficiency",
        "description": "Failure to establish or implement an adequate corrective and preventive action system, including failure to identify root causes, implement effective corrections, or verify effectiveness of actions taken.",
        "keywords": ["corrective action", "preventive action", "capa", "corrective and preventive", "recurrence", "effectiveness check"],
        "primary_cfr": ["21 CFR 820.100", "21 CFR 211.192", "ICH Q10"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["CAPA", "Deviation", "SOP"],
        "root_cause_categories": ["system_failure", "inadequate_investigation", "management_oversight"],
        "evidence_indicators": [
            "CAPA effectiveness not verified",
            "Root cause identified as 'human error' without systemic investigation",
            "Same finding recurring across assessments",
            "CAPA closed without implementation evidence",
            "Preventive action missing",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1", "SS-B2", "SS-MD1"],
    },
    {
        "id": "FM-003",
        "name": "Written Procedure Gap",
        "description": "Absence of required written procedures or SOPs, or procedures that are inadequate, not followed, or not approved by quality unit.",
        "keywords": ["written procedure", "standard operating", "sop", "procedure not established", "failed to establish written", "no written", "lack of written"],
        "primary_cfr": ["21 CFR 211.100", "21 CFR 211.22", "21 CFR 820.40"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation"],
        "root_cause_categories": ["documentation_gap", "management_oversight", "procedure_inadequacy"],
        "evidence_indicators": [
            "No written procedure for critical operation",
            "Procedure not approved by quality unit",
            "Outdated procedure not reviewed",
            "Procedure not followed as written",
            "Procedure lacks adequate specificity",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1", "SS-B2", "SS-MD1", "SS-DX1"],
    },
    {
        "id": "FM-004",
        "name": "Data Integrity Violation",
        "description": "Failure to ensure ALCOA+ principles (Attributable, Legible, Contemporaneous, Original, Accurate), including audit trail manipulation, backdating, unauthorized changes, or deletion of raw data.",
        "keywords": ["data integrity", "audit trail", "falsif", "alterat", "backdating", "unauthorized chang", "raw data deleted", "data manipulat", "contemporaneous", "attributable"],
        "primary_cfr": ["21 CFR 211.68", "21 CFR 211.194", "21 CFR 211.100"],
        "severity_range": ["critical"],
        "doc_categories": ["ATM", "LIR", "SOP", "Validation"],
        "root_cause_categories": ["data_integrity", "management_oversight", "inadequate_training"],
        "evidence_indicators": [
            "Audit trail disabled or not reviewed",
            "Records altered without justification",
            "Original data not retained",
            "Electronic records do not meet 21 CFR Part 11",
            "Test results recorded after the fact",
            "Raw data deleted or overwritten",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1"],
    },
    {
        "id": "FM-005",
        "name": "Training and Qualification Failure",
        "description": "Personnel performing critical operations without documented training, qualification, or demonstrated competency. Includes study directors, analysts, and supervisory personnel.",
        "keywords": ["training", "qualification", "competency", "education and experience", "trained personnel", "job description", "training record"],
        "primary_cfr": ["21 CFR 211.34", "21 CFR 58.29", "21 CFR 820.25"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP"],
        "root_cause_categories": ["inadequate_training", "management_oversight", "documentation_gap"],
        "evidence_indicators": [
            "No training records for personnel performing critical tasks",
            "Training completed after performing procedure",
            "Protocol-specific training not documented",
            "Study director not qualified",
            "Training effectiveness not assessed",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-B1", "SS-B2", "SS-MD1"],
    },
    {
        "id": "FM-006",
        "name": "Process Validation Deficiency",
        "description": "Failure to validate or qualify critical manufacturing processes, equipment, or computer systems. Includes inadequate process performance qualification or revalidation after changes.",
        "keywords": ["process validation", "validation protocol", "process performance qualif", "revalidat", "qualification protocol", "cleaning validation", "method validation"],
        "primary_cfr": ["21 CFR 211.100", "21 CFR 820.75", "21 CFR 211.68"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["Validation", "SOP"],
        "root_cause_categories": ["validation_gap", "change_control_failure", "technical_deficiency"],
        "evidence_indicators": [
            "Process not validated before commercial distribution",
            "Validation not re-performed after significant change",
            "Cleaning validation inadequate",
            "Analytical method not validated",
            "Computer system validation not current",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1", "SS-MD1"],
    },
    {
        "id": "FM-007",
        "name": "Complaint Handling and MDR Failure",
        "description": "Failure to adequately investigate customer complaints, file required Medical Device Reports (MDRs), or implement corrections from complaint signals.",
        "keywords": ["complaint", "consumer complaint", "MDR", "medical device report", "adverse event report", "malfunction report", "803."],
        "primary_cfr": ["21 CFR 820.198", "21 CFR 803.17", "21 CFR 803.50"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["CAPA", "Deviation"],
        "root_cause_categories": ["complaint_system_failure", "reporting_failure", "inadequate_investigation"],
        "evidence_indicators": [
            "MDR not filed within required timeframe",
            "Complaint not investigated",
            "No trending of complaint data",
            "Adverse event not reported",
            "Complaint files incomplete",
        ],
        "sub_sectors": ["SS-MD1", "SS-DX1", "SS-D1", "SS-D2"],
    },
    {
        "id": "FM-008",
        "name": "Stability Program Failure",
        "description": "Absence or inadequacy of stability testing program including failure to establish expiry dating, conduct required testing, or respond to stability failures.",
        "keywords": ["stability", "shelf life", "expiry", "expiration dating", "stability testing", "stability protocol", "stability study"],
        "primary_cfr": ["21 CFR 211.166", "21 CFR 211.137"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["ATM", "Validation", "SOP"],
        "root_cause_categories": ["documentation_gap", "analytical_method_failure", "program_deficiency"],
        "evidence_indicators": [
            "No stability protocol established",
            "Insufficient stability data to support expiry",
            "Stability failures not investigated",
            "Stability testing not performed at required intervals",
            "No ongoing stability program",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4"],
    },
    {
        "id": "FM-009",
        "name": "Contamination Control Failure",
        "description": "Failure to prevent microbial, cross-contamination, or environmental contamination. Includes inadequate environmental monitoring, aseptic practices, or facility/equipment cleaning.",
        "keywords": ["contamination", "microbial", "sterility", "aseptic", "environmental monitoring", "bioburden", "endotoxin", "particulate"],
        "primary_cfr": ["21 CFR 211.42", "21 CFR 211.113", "21 CFR 211.67"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["SOP", "Validation", "ATM"],
        "root_cause_categories": ["facility_design", "procedure_inadequacy", "training_gap"],
        "evidence_indicators": [
            "Environmental monitoring failures not investigated",
            "Inadequate aseptic technique",
            "Cleaning and disinfection procedures deficient",
            "Air classification not qualified",
            "Personnel monitoring excursions unaddressed",
        ],
        "sub_sectors": ["SS-D3", "SS-B1", "SS-B2", "SS-VAC"],
    },
    {
        "id": "FM-010",
        "name": "Component and Supplier Quality Failure",
        "description": "Failure to test incoming materials, qualify suppliers, or establish specifications for components used in manufacturing.",
        "keywords": ["supplier", "vendor qualification", "component testing", "raw material testing", "incoming material", "approved supplier"],
        "primary_cfr": ["21 CFR 211.84", "21 CFR 820.50"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "ATM"],
        "root_cause_categories": ["supplier_management", "documentation_gap", "procedure_inadequacy"],
        "evidence_indicators": [
            "Components used without identity testing",
            "Supplier not qualified or approved",
            "Certificate of Analysis not verified",
            "Component specifications not established",
            "No supplier audit program",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-MD1"],
    },
    {
        "id": "FM-011",
        "name": "Nonconforming Product Control Failure",
        "description": "Failure to identify, segregate, and properly disposition nonconforming products or materials to prevent inadvertent use or distribution.",
        "keywords": ["nonconforming", "reject", "disposition", "quarantine", "non-conforming", "failed product", "rejected batch"],
        "primary_cfr": ["21 CFR 820.90", "21 CFR 211.165", "21 CFR 211.192"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["Deviation", "CAPA", "SOP"],
        "root_cause_categories": ["system_failure", "documentation_gap", "procedure_inadequacy"],
        "evidence_indicators": [
            "Nonconforming product not quarantined",
            "Disposition decision not documented",
            "Nonconforming product distributed",
            "Rejection criteria not established",
            "No procedure for nonconforming disposition",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-MD1"],
    },
    {
        "id": "FM-012",
        "name": "Equipment and Instrument Failure",
        "description": "Failure to maintain, calibrate, or qualify equipment and instruments used in manufacturing or quality control testing.",
        "keywords": ["calibration", "equipment qualification", "equipment maintenance", "out of calibration", "preventive maintenance", "instrument qualification"],
        "primary_cfr": ["21 CFR 211.68", "21 CFR 211.67", "21 CFR 820.70"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation", "ATM"],
        "root_cause_categories": ["maintenance_failure", "documentation_gap", "procedure_inadequacy"],
        "evidence_indicators": [
            "Equipment used without current calibration",
            "No preventive maintenance schedule",
            "Equipment qualification not performed",
            "Out-of-calibration equipment used for testing",
            "Calibration records incomplete",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1", "SS-MD1"],
    },
    {
        "id": "FM-013",
        "name": "Change Control Failure",
        "description": "Failure to control or document changes to processes, equipment, software, materials, or specifications through a formal change control system.",
        "keywords": ["change control", "unauthorized change", "design change", "specification change", "change not approved", "undocumented change"],
        "primary_cfr": ["21 CFR 820.30", "21 CFR 211.100", "21 CFR 211.68"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation"],
        "root_cause_categories": ["change_control_failure", "management_oversight", "documentation_gap"],
        "evidence_indicators": [
            "Change implemented without formal review",
            "No impact assessment for change",
            "Post-change validation not performed",
            "Unauthorized software configuration change",
            "Change not communicated to affected functions",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-MD1"],
    },
    {
        "id": "FM-014",
        "name": "Quality Unit Authority Failure",
        "description": "Failure of the quality unit to fulfill its responsibility to approve or reject products, procedures, specifications, or to have adequate authority over quality systems.",
        "keywords": ["quality unit", "quality control unit", "211.22", "quality assurance", "qau", "qc unit approval", "qcu"],
        "primary_cfr": ["21 CFR 211.22", "21 CFR 820.20"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["SOP", "CAPA"],
        "root_cause_categories": ["management_oversight", "system_failure", "organizational_failure"],
        "evidence_indicators": [
            "Quality unit does not have final authority",
            "Batch released without quality unit approval",
            "Quality unit responsibilities not defined",
            "Quality unit not adequately staffed",
            "SOPs not approved by quality unit",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4", "SS-B1"],
    },
    {
        "id": "FM-015",
        "name": "Risk Management System Deficiency",
        "description": "Absence or inadequacy of risk management activities including risk assessments, FMEA, hazard analysis, or failure to incorporate risk signals into quality decisions.",
        "keywords": ["risk management", "risk analysis", "risk assessment", "FMEA", "hazard analysis", "risk-based", "risk control"],
        "primary_cfr": ["21 CFR 820.30", "ICH Q9", "ISO 14971"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation", "CAPA"],
        "root_cause_categories": ["system_failure", "management_oversight", "technical_deficiency"],
        "evidence_indicators": [
            "No risk assessment for process changes",
            "Risk management not updated after failures",
            "FMEA not performed for critical processes",
            "Risk controls not verified for effectiveness",
            "Hazard analysis incomplete",
        ],
        "sub_sectors": ["SS-MD1", "SS-DX1", "SS-D1", "SS-D2"],
    },
    {
        "id": "FM-016",
        "name": "Batch Record and Documentation Failure",
        "description": "Failure to maintain complete, accurate batch production records, laboratory records, or to document critical manufacturing steps contemporaneously.",
        "keywords": ["batch record", "production record", "batch production", "laboratory record", "incomplete record", "documentation failure", "211.188"],
        "primary_cfr": ["21 CFR 211.188", "21 CFR 211.194", "21 CFR 211.186"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "ATM", "LIR"],
        "root_cause_categories": ["documentation_gap", "data_integrity", "training_gap"],
        "evidence_indicators": [
            "Batch records incomplete or missing entries",
            "Critical steps not documented at time of performance",
            "Batch record review inadequate",
            "Laboratory records do not contain all required elements",
            "Records not retained for required period",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-D4"],
    },
    {
        "id": "FM-017",
        "name": "Design Control Failure (Medical Devices)",
        "description": "Failure to establish and maintain adequate design controls including design review, verification, validation, and design transfer for medical devices.",
        "keywords": ["design control", "design review", "design verification", "design validation", "design transfer", "820.30"],
        "primary_cfr": ["21 CFR 820.30"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["SOP", "Validation"],
        "root_cause_categories": ["design_failure", "validation_gap", "documentation_gap"],
        "evidence_indicators": [
            "Design verification not performed",
            "Design validation not performed on final product",
            "Design history file incomplete",
            "No design review records",
            "Design transfer to manufacturing not controlled",
        ],
        "sub_sectors": ["SS-MD1", "SS-DX1"],
    },
    {
        "id": "FM-018",
        "name": "Labeling Control Failure",
        "description": "Failure to control labeling operations, including mislabeling, inadequate label reconciliation, or distribution of products with incorrect or missing labels.",
        "keywords": ["labeling control", "label reconciliation", "mislabeling", "labeling operation", "label issuance", "label mix-up"],
        "primary_cfr": ["21 CFR 211.130", "21 CFR 211.125", "21 CFR 211.122"],
        "severity_range": ["high", "critical"],
        "doc_categories": ["SOP", "Deviation"],
        "root_cause_categories": ["procedure_inadequacy", "training_gap", "system_failure"],
        "evidence_indicators": [
            "Label reconciliation not performed",
            "Incorrect labels used for product",
            "Labels not controlled or stored securely",
            "Label examination inadequate",
            "Dispensing of labels not documented",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3"],
    },
    {
        "id": "FM-019",
        "name": "Facility and Environmental Failure",
        "description": "Failure to maintain facilities in good repair, with adequate space, lighting, or environmental controls to support manufacturing operations.",
        "keywords": ["facility", "building", "sanitation", "pest control", "adequate space", "environmental control", "HVAC", "air handling"],
        "primary_cfr": ["21 CFR 211.42", "21 CFR 211.56", "21 CFR 211.58"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation"],
        "root_cause_categories": ["facility_design", "maintenance_failure", "management_oversight"],
        "evidence_indicators": [
            "Facility not maintained in clean condition",
            "Inadequate separation between operations",
            "HVAC system not qualified",
            "Pest control program deficient",
            "Inadequate lighting for operations",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-B1"],
    },
    {
        "id": "FM-020",
        "name": "Electronic Records and Part 11 Failure",
        "description": "Failure to implement controls required for electronic records and electronic signatures under 21 CFR Part 11, including audit trails, access controls, and system validation.",
        "keywords": ["electronic record", "21 CFR part 11", "part 11", "electronic signature", "audit trail", "access control", "system validation", "computer system"],
        "primary_cfr": ["21 CFR 11.10", "21 CFR 11.30", "21 CFR 211.68"],
        "severity_range": ["medium", "high"],
        "doc_categories": ["SOP", "Validation"],
        "root_cause_categories": ["system_failure", "validation_gap", "documentation_gap"],
        "evidence_indicators": [
            "Audit trail not enabled or not reviewed",
            "Shared login credentials",
            "Electronic records not protected from alteration",
            "System not validated for intended use",
            "Electronic signatures not linked to records",
        ],
        "sub_sectors": ["SS-D1", "SS-D2", "SS-D3", "SS-B1", "SS-MD1"],
    },
]


def _cfr_section(citation_str: str) -> str | None:
    m = re.search(r'(\d+\.\d+)', citation_str)
    return m.group(1) if m else None


def build_failure_modes(observations: list[dict]) -> list[dict]:
    """Match each observation to failure modes and build aggregated records."""
    # Build per-mode accumulators
    mode_data: dict[str, dict] = {}
    for fm in FAILURE_MODE_DEFS:
        mode_data[fm["id"]] = {
            "matched_count": 0,
            "cfr_frequency": Counter(),
            "example_obs_ids": [],
            "company_ids": set(),
            "years": Counter(),
            "offices": Counter(),
        }

    # Match observations to modes
    for obs in observations:
        text_lower = obs.get("text", "").lower()
        cfr_secs = [_cfr_section(c) for c in obs.get("cfr_citations", []) if _cfr_section(c)]
        obs_id = obs.get("id", "")
        company = obs.get("company", "")
        year = obs.get("year", "")
        office = obs.get("office", "")

        for fm in FAILURE_MODE_DEFS:
            if any(kw.lower() in text_lower for kw in fm["keywords"]):
                md = mode_data[fm["id"]]
                md["matched_count"] += 1
                for sec in cfr_secs:
                    md["cfr_frequency"][sec] += 1
                if len(md["example_obs_ids"]) < 10:
                    md["example_obs_ids"].append(obs_id)
                md["company_ids"].add(company)
                if year:
                    md["years"][year] += 1
                if office:
                    md["offices"][office] += 1

    # Build output records
    records = []
    for fm in FAILURE_MODE_DEFS:
        md = mode_data[fm["id"]]
        top_cfr = [sec for sec, _ in md["cfr_frequency"].most_common(8)]
        years_sorted = sorted(md["years"].keys())

        records.append({
            "id": fm["id"],
            "name": fm["name"],
            "description": fm["description"],
            "frequency": md["matched_count"],
            "primary_cfr_citations": fm["primary_cfr"],
            "observed_cfr_sections": top_cfr,
            "severity_range": fm["severity_range"],
            "doc_categories": fm["doc_categories"],
            "sub_sectors": fm["sub_sectors"],
            "root_cause_categories": fm["root_cause_categories"],
            "evidence_indicators": fm["evidence_indicators"],
            "example_observation_ids": md["example_obs_ids"],
            "affected_companies_count": len(md["company_ids"]),
            "observation_years": years_sorted,
            "offices": dict(md["offices"]),
            "keywords": fm["keywords"],
            "agency": "FDA",
            "is_current": True,
        })

    records.sort(key=lambda r: -r["frequency"])
    return records


def main():
    print(f"Loading observations from {OBS_PATH}...")
    observations = []
    with open(OBS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                observations.append(json.loads(line))
    print(f"  Loaded {len(observations)} observations")

    print("\nBuilding failure mode library...")
    records = build_failure_modes(observations)

    print(f"\nFailure modes ({len(records)}):")
    for r in records:
        print(f"  {r['id']} {r['name']}: {r['frequency']} observations, "
              f"{r['affected_companies_count']} companies")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nWritten to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
