"""
Evidence Package Completeness Service.
Checks whether a BatchDossier contains all documents expected for its
record family, product type, and sterility classification.
"""

# Default evidence templates by record family
# Format: { record_family: { required: [...roles], optional: [...roles], sterile_adds: [...roles] } }
DEFAULT_TEMPLATES = {
    "pharma_bpr": {
        "required": ["primary_bpr"],
        "conditional": {
            # If any deviation is referenced in the primary BPR, a deviation document is required
            "deviation": "Referenced deviation reports",
            "qc_result": "QC release test results or COA",
        },
        "optional": ["capa", "coa", "equipment_log", "packaging_record", "labeling_record"],
        "sterile_adds_required": ["environmental_monitoring", "filter_integrity", "sterilization_record"],
    },
    "api_batch": {
        "required": ["primary_bpr"],
        "conditional": {
            "deviation": "Referenced deviation reports",
            "qc_result": "QC release test results or COA",
        },
        "optional": ["coa", "equipment_log"],
        "sterile_adds_required": [],
    },
    "biologics_batch": {
        "required": ["primary_bpr"],
        "conditional": {
            "deviation": "Referenced deviation reports",
            "qc_result": "QC release test results including potency/purity",
        },
        "optional": ["coa", "environmental_monitoring", "equipment_log"],
        "sterile_adds_required": ["environmental_monitoring", "filter_integrity", "sterilization_record"],
    },
    "sterile_batch": {
        "required": ["primary_bpr", "environmental_monitoring", "filter_integrity"],
        "conditional": {
            "deviation": "Referenced deviation reports",
            "qc_result": "Sterility, endotoxin, and potency results",
        },
        "optional": ["sterilization_record", "equipment_log"],
        "sterile_adds_required": [],
    },
    "device_dhr": {
        "required": ["primary_bpr"],
        "conditional": {
            "deviation": "Nonconformance records if applicable",
            "qc_result": "Final inspection and acceptance records",
        },
        "optional": ["labeling_record", "packaging_record"],
        "sterile_adds_required": ["sterilization_record"],
    },
    "supplement_bpr": {
        "required": ["primary_bpr"],
        "conditional": {
            "qc_result": "Identity, potency, and finished product specifications",
        },
        "optional": ["coa", "labeling_record"],
        "sterile_adds_required": [],
    },
    "cell_therapy": {
        "required": ["primary_bpr"],
        "conditional": {
            "qc_result": "Viability, identity, potency, and sterility results",
            "coa": "Chain-of-identity and chain-of-custody documentation",
        },
        "optional": ["environmental_monitoring", "equipment_log"],
        "sterile_adds_required": ["environmental_monitoring"],
    },
    "cdmo_package": {
        "required": ["primary_bpr"],
        "conditional": {
            "deviation": "Deviation and investigation reports",
            "qc_result": "COA and QC test results",
            "coa": "Certificates of Analysis",
        },
        "optional": ["environmental_monitoring", "equipment_log", "packaging_record"],
        "sterile_adds_required": ["environmental_monitoring", "filter_integrity", "sterilization_record"],
    },
}

ROLE_LABELS = {
    "primary_bpr": "Primary Batch/Production Record",
    "deviation": "Deviation / Investigation Report",
    "capa": "CAPA Record",
    "qc_result": "QC Test Results",
    "coa": "Certificate of Analysis (COA)",
    "environmental_monitoring": "Environmental Monitoring Records",
    "equipment_log": "Equipment Log / Cleaning Record",
    "reprocessing_record": "Reprocessing / Rework Documentation",
    "sterilization_record": "Sterilization Cycle Record",
    "filter_integrity": "Filter Integrity Test Record",
    "packaging_record": "Packaging Record",
    "labeling_record": "Labeling / Label Reconciliation Record",
    "other": "Other Supporting Document",
}


class EvidenceCompletenessService:
    """
    Checks evidence package completeness for a batch dossier.
    Returns a structured assessment of what's present, missing, and conditional.
    """

    def check(self, dossier, dossier_documents: list) -> dict:
        """
        Evaluate evidence completeness for a dossier.

        Returns:
            {
                "complete": bool,
                "present_roles": [...],
                "missing_required": [...],
                "missing_conditional": {...},  # role -> reason why expected
                "optional_present": [...],
                "optional_missing": [...],
                "summary": str,
            }
        """
        record_family = getattr(dossier, "record_family", "pharma_bpr") or "pharma_bpr"
        is_sterile = getattr(dossier, "is_sterile", False) or False

        template = DEFAULT_TEMPLATES.get(record_family, DEFAULT_TEMPLATES["pharma_bpr"])

        present_roles = {dd.role for dd in dossier_documents}

        # Required documents
        required = list(template["required"])
        if is_sterile and template.get("sterile_adds_required"):
            required = list(set(required + template["sterile_adds_required"]))

        missing_required = [r for r in required if r not in present_roles]

        # Conditional documents (flagged as expected but not hard-blocked)
        conditional = template.get("conditional", {})
        missing_conditional = {
            role: reason
            for role, reason in conditional.items()
            if role not in present_roles
        }

        # Optional
        optional = template.get("optional", [])
        optional_present = [o for o in optional if o in present_roles]
        optional_missing = [o for o in optional if o not in present_roles]

        complete = len(missing_required) == 0

        parts = []
        if missing_required:
            labels = [ROLE_LABELS.get(r, r) for r in missing_required]
            parts.append(f"Missing required: {', '.join(labels)}")
        if missing_conditional:
            labels = [ROLE_LABELS.get(r, r) for r in missing_conditional]
            parts.append(f"Expected but not uploaded: {', '.join(labels)}")
        summary = "; ".join(parts) if parts else "Evidence package complete"

        return {
            "complete": complete,
            "present_roles": sorted(present_roles),
            "missing_required": missing_required,
            "missing_required_labels": [ROLE_LABELS.get(r, r) for r in missing_required],
            "missing_conditional": missing_conditional,
            "optional_present": optional_present,
            "optional_missing": optional_missing,
            "summary": summary,
        }
