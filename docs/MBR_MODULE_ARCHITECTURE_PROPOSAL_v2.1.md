# Clyira Batch & Lot Record Review Module

## Architecture Proposal v2.1

**Date:** May 28, 2026
**Author:** Clyira Product Team
**Status:** DRAFT — Pending Product Owner Decision
**Classification:** Internal / Confidential
**Initial Use Case:** Pharmaceutical MBR / Batch Production Record Review
**Changelog:**
- v1.0 — Initial architecture based on codebase analysis and regulatory requirements
- v2.0 — Competitive intelligence from 10+ competitors; added IDP Engine, three-tier OCR→ICR→IWR, three-color verification, 4-tier disposition, knowledge graph consideration, CPV/SPC trending, explainability
- v2.1 — Cross-sector stress test; renamed module; added Layer 0 sector routing, modular review packs, evidence package completeness gate, Gray verification state, disposition readiness reframing, synthetic test library, validation strategy, CDMO multi-sponsor architecture, field criticality model, provider-agnostic IDP

---

## Table of Contents

1. Product Definition (Updated — broadened scope)
2. Sector Routing & Record Family Taxonomy (NEW)
3. Competitive Intelligence
4. User Roles (Updated — CDMO roles added)
5. Core User Workflow (Updated — evidence completeness gate, readiness reframing)
6. Processing Pipeline (Updated — Layer 0 added)
7. IDP Engine Architecture (Updated — provider-agnostic)
8. Handwriting and Scan Strategy
9. Modular Review Packs (NEW — replaces monolithic rule engine section)
10. Field Criticality Model (NEW)
11. Finding Model (Updated — Gray state, dual confidence)
12. Human Review Controls (Updated — 4-state verification)
13. Disposition Readiness Model (Updated — readiness, not recommendation)
14. Knowledge Graph Consideration
15. Cross-Batch CPV/SPC Trending
16. Explainability and Auditability (Updated — dropped SHAP label)
17. CDMO & Multi-Sponsor Architecture (NEW)
18. Data Model Proposal (Updated)
19. UI Proposal (Updated)
20. Synthetic Test Library (NEW)
21. Validation Strategy (NEW)
22. Additional Design Considerations — Stress Test Gaps (NEW)
23. Phased Implementation (Updated)
24. Risks and Open Questions (Updated)
25. Recommendation (Updated)
26. Appendix: Codebase Inventory

---

## 1. Product Definition

### 1.1 What This Module Is

The Batch & Lot Record Review module is an AI-assisted review support tool that helps QA reviewers process regulated production records — batch production records (BPRs), device history records (DHRs), and related quality documentation — by organizing records into structured, evidence-linked review packages, surfacing potential issues, and requiring human verification before any disposition decision.

The module is sector-aware: it recognizes that different life science sectors use different terminology, different record structures, and different regulatory frameworks for what is fundamentally the same problem — reviewing executed production records for completeness, accuracy, and compliance before lot disposition.

| Sector | Record Names | Primary Regulation |
|---|---|---|
| Pharma / drug product | MBR, BMR, BPR, executed batch record | 21 CFR 211.186-192 |
| Biologics / vaccines | BPR, batch record with bioprocess steps | 21 CFR 211 + ICH Q5/Q6B |
| Sterile / aseptic | BPR with aseptic processing documentation | 21 CFR 211 + FDA Aseptic Guidance |
| API manufacturing | API batch record | ICH Q7 |
| Medical devices | DHR (Device History Record) | 21 CFR 820.184 |
| Dietary supplements | BPR / MMR (Master Manufacturing Record) | 21 CFR 111.255-260 |
| Cell / gene therapy | COI/COC patient lot dossier | 21 CFR 1271 + sector guidance |
| Blood / plasma / HCT/P | Collection, processing, testing records | 21 CFR 606.160, 1271 |
| CDMO / CTL | Sponsor lot package, CoA package, deviation packet | Sponsor quality agreement + applicable GMP |

**Initial use case (Phases 1-2):** Pharmaceutical MBR/BPR review. The architecture is designed to extend to all sectors above through modular review packs (see Section 9), but the first product ships for pharma batch records.

### 1.2 What This Module Is NOT

This module does NOT:

- Replace MES (Manufacturing Execution System) or eBR (Electronic Batch Record) systems
- Make disposition decisions — final QA disposition is always a human-owned decision
- Replace human QA review — it supports and augments reviewers
- Provide "fully automated QA" or "guaranteed compliance"
- Generate batch records — it reviews records that have already been executed
- Function as a real-time shop floor data capture system
- Recommend "release" or "reject" — it assesses readiness for human QA disposition review

### 1.3 Why It Fits Clyira

Clyira's existing architecture is built for exactly this type of work. The platform already:

- Accepts document uploads (PDF, DOCX) via `DocumentService.upload_document()`
- Extracts text using pdfplumber (primary) and PyPDF2 (fallback) in `_extract_text_from_bytes()`
- Identifies sections heuristically via `_identify_sections()`
- Auto-classifies documents into categories via `_auto_classify()`
- Resolves Document Type Assessment Profiles (DTAPs) via `DTAPRegistry.resolve()`
- Runs an 11-level neuro-symbolic assessment pipeline via `AssessmentOrchestrator.run_assessment()`
- Matches findings against FDA enforcement precedents via `EnforcementEngine`
- Produces scored, evidence-linked findings with remediation suggestions
- Stores everything in a Part 11-compliant audit trail with tamper-evident hashing

The module leverages ALL of this existing infrastructure. A batch record uploaded today would flow through the same pipeline as a CAPA or deviation — just with different checks defined in a different DTAP profile, composed from the appropriate review packs.

### 1.4 How It Differs from Competitors

| Dimension | MES/eBR (Apprentice, Tulip) | IDP/Extraction (Acodis) | AI Batch Review (Mareana, Aizon) | Clyira Module |
|---|---|---|---|---|
| Primary function | Execute and capture during manufacturing | Extract structured data from documents | AI-powered review and anomaly detection | Assess completed records for compliance gaps + lot-level readiness |
| Sector scope | Pharma only | Multi-sector (IDP is sector-agnostic) | Pharma + biotech | Multi-sector via modular review packs |
| When in lifecycle | During manufacturing | Post-manufacturing extraction | Post-manufacturing review | Post-manufacturing, supports disposition review |
| Scope | Single batch record | Single batch record | Single batch or cross-batch trends | Batch dossier: BPR + deviations + CAPAs + QC + evidence package |
| Output | Completed eBR | Extracted data + exceptions | Anomaly alerts + dashboards | Scored findings + enforcement matches + disposition readiness |
| Cross-document | No | No | Limited | Yes (lot-level cross-reference with dossier + evidence completeness) |
| Regulatory intelligence | None | Limited | Varies | Full L1-L11 including L9 enforcement pattern matching |
| Explainability | N/A | Field-level confidence | Varies (Aizon has SHAP) | Structured explanation trace per finding + evidence linking |
| Disposition model | Binary pass/fail | N/A | Varies | 4-tier readiness: Ready / Conditional / Not Ready / Hold |
| Knowledge graph | No | No | Yes (Mareana) | Phase 5+ consideration |
| Handwriting | N/A (digital) | ICR+IWR with HITL | Limited | Three-tier OCR→ICR→IWR with confidence gating (Phase 4) |

### 1.5 Competitive Positioning

Clyira sits at the intersection of two capabilities no competitor bridges:

- **ML Document Automation** — Provider-agnostic IDP engine for extraction (pluggable: AWS Textract, Google Document AI, Azure, or open-source)
- **Rule-Based Compliance Enforcement** — DTAP-driven deterministic assessment with regulatory intelligence

Clyira's moat is NOT IDP/extraction (that's commoditizing). Clyira's moat is QA review logic — the combination of DTAP profiles, sector-specific review packs, enforcement pattern matching, longitudinal analysis, and the Batch Dossier concept with evidence completeness gating.

The Batch Dossier with evidence package completeness is something no competitor currently offers: a single lot-level view that connects the production record to all supporting quality evidence, verifies the evidence set is complete for the product/process type, and presents a structured readiness assessment for human QA disposition.

### 1.6 Compliance Positioning (Critical)

All language in the module, UI, reports, and API responses MUST use safe language:

**Use:** AI-assisted review, potential issue, human verification required, reviewer confirmation needed, evidence-linked finding, final QA decision remains human-owned, supports reviewer decision, review support tool, disposition readiness, evidence completeness

**Never use:** AI approved, batch released, fully automated QA, no human review needed, guaranteed compliant, FDA-compliant by default, release recommendation, reject recommendation

This is especially critical given FDA's April 2026 Purolea warning letter — the first enforcement action citing AI over-reliance. Clyira must position itself as a tool that enhances human review, never replaces it.

### 1.7 Data Privacy Commitment

Following CPV-Auto's explicit policy model: Clyira does NOT train on client data. Customer production records, assessments, and corrections are never used to train foundation models. This is a documented, auditable policy — not a verbal assurance. Client data stays within the client's tenant boundary and is used only for that client's assessments and longitudinal analysis.

### 1.8 Investor / Customer Positioning

**Platform story:**
Clyira converts regulated production records — batch records, device history records, QC records, and supporting quality documents — into structured, evidence-linked review packages. It does not replace MES, LIMS, QMS, or human QA. It helps QA teams verify whether the lot record is complete, defensible, and ready for disposition review.

**First wedge:**
We start with pharma batch records and CDMO batch packages, where review delays, missing evidence, and weak deviation linkage directly slow release and create inspection risk.

---

## 2. Sector Routing & Record Family Taxonomy (NEW in v2.1)

### 2.1 Layer 0: Product/Process Classification

Before any assessment runs, the system must classify the record to determine which review packs activate. This is Layer 0 — it runs before L1-L11 and determines the assessment context.

**Classification dimensions:**

| Dimension | Options | Impact |
|---|---|---|
| **Record family** | Pharma BMR/BPR, API batch record, Biologics batch record, Sterile/aseptic record, Device DHR, Dietary supplement BPR/MMR, Cell therapy COI/COC, Blood/plasma/HCT/P record, CDMO sponsor package | Determines which sector pack activates |
| **Product type** | Small molecule, biologic, vaccine, API, combination product, dietary supplement, medical device, cell therapy, gene therapy | Determines CPP/CQA expectations and regulatory references |
| **Sterility** | Sterile vs. non-sterile | If sterile, activates Sterile/Aseptic Review Pack |
| **Manufacturing context** | Internal site vs. CDMO-received | If CDMO, activates sponsor oversight checks |
| **Batch purpose** | Commercial, validation (PPQ), exhibit (regulatory filing), stability, tech transfer, clinical, scale-up | Determines review rigor level and specific checks |
| **Record format** | Digital PDF (eBR export), scanned paper, hybrid (paper + digital), handwritten | Determines IDP pipeline routing |

### 2.2 How Classification Works

**Phase 1 (MVP):** Manual classification. When creating a BatchDossier, the user selects product type, sterility, manufacturing context, and batch purpose from dropdowns. The system resolves the appropriate DTAP profile and review pack composition.

**Phase 2+:** Semi-automatic classification. The IDP Engine analyzes the uploaded document and suggests a classification based on detected content (regulatory references, section headers, terminology). The user confirms or corrects.

### 2.3 Classification → Review Pack Resolution

```
Layer 0 Classification
│
├── Record family = Pharma BMR/BPR
│   ├── Always: Core Production Record Pack
│   ├── Always: Pharma Drug Product Pack
│   ├── If sterile: + Sterile/Aseptic Pack
│   ├── If CDMO-received: + CDMO Sponsor Oversight Pack
│   └── If exhibit batch: heightened rigor settings
│
├── Record family = API batch record
│   ├── Always: Core Production Record Pack
│   ├── Always: API Manufacturing Pack
│   └── If CDMO-received: + CDMO Sponsor Oversight Pack
│
├── Record family = Biologics batch record
│   ├── Always: Core Production Record Pack
│   ├── Always: Pharma Drug Product Pack
│   ├── Always: Biologics Pack
│   ├── If sterile: + Sterile/Aseptic Pack
│   └── If CDMO-received: + CDMO Sponsor Oversight Pack
│
├── Record family = Device DHR
│   ├── Always: Core Production Record Pack
│   ├── Always: Device DHR Pack
│   ├── If sterile device: + Sterile/Aseptic Pack
│   └── If combination product: + Pharma Drug Product Pack
│
├── Record family = Dietary supplement BPR/MMR
│   ├── Always: Core Production Record Pack
│   └── Always: Dietary Supplement Pack
│
├── Record family = Cell therapy COI/COC
│   ├── Always: Core Production Record Pack
│   └── Always: Cell Therapy COI/COC Pack
│
└── [Future sector families follow same pattern]
```

This maps directly to Clyira's existing DTAP architecture. Each "review pack" is a DTAP overlay — a set of checks that compose additively on top of the Core Pack. The `DTAPRegistry.resolve()` method already supports profile composition.

---

## 3. Competitive Intelligence

### 3.1 Competitor Landscape

Research across 10+ competitor products, consulting frameworks, and industry analyses identified design patterns that inform Clyira's architecture. The competitors fall into four categories:

**Category 1: MES / eBR Execution Platforms**
- Tulip, Apprentice.io, MasterControl — Real-time shop floor capture, not post-hoc review
- Key takeaway: Tulip's "Review by Exception" (RBE) pattern — QA reviews only the 1-2% of flagged exceptions, not every page. Maps to Clyira's finding severity system.

**Category 2: IDP / Document Extraction**
- Acodis — Foundation model-based IDP with ICR, complex table extraction, and HITL verification
- Key takeaway: IDP must be a separate engine from assessment. Extraction confidence and assessment confidence are distinct. IDP is commoditizing — Clyira's moat should be QA logic, not extraction.

**Category 3: AI-Powered Batch Review / CPV**
- Mareana — GraphRAG over validated knowledge graph ("genealogy"), three-color verification
- Aizon — Real-time process monitoring with ML explainability
- CPV-Auto — Automated CPV/SPC trending with explicit no-training-on-client-data policy
- Key takeaways: Knowledge graph constrains AI to validated data. Cross-batch trending is table-stakes for pharma QA.

**Category 4: Consulting Frameworks / Industry Analysis**
- PwC — AI GxP compliance framework: GAMP 5 validation, explainability as non-negotiable
- A&M — Case study showing 40% cycle time reduction from AI-powered batch record mining
- Assyro — 4-tier disposition model (Release/Conditional/Hold/Reject) and common errors
- CDMO World — Human error analysis: most batch record issues are documentation errors, not manufacturing errors

### 3.2 Design Patterns Extracted (12 patterns, all incorporated)

| # | Pattern | Source | Clyira Integration |
|---|---|---|---|
| 1 | Review by Exception (RBE) | Tulip | Finding severity drives review scope |
| 2 | IDP as separate engine | Acodis | Provider-agnostic IDP layer (Section 7) |
| 3 | Three-tier OCR→ICR→IWR | Acodis | Phased handwriting pipeline (Section 8) |
| 4 | Dual confidence scoring | Acodis | Extraction confidence vs. finding confidence (Section 11) |
| 5 | Complex table extraction | Acodis | Table recognition in IDP (Section 7) |
| 6 | GraphRAG over knowledge graph | Mareana | Phase 5+ consideration (Section 14) |
| 7 | Multi-state verification | Mareana | Green/Red/Blue/Gray 4-state model (Section 12) |
| 8 | Shadow/parallel review mode | Tulip | Calibration before go-live (Section 12) |
| 9 | Disposition readiness model | Assyro | Ready/Conditional/Not Ready/Hold (Section 13) |
| 10 | Cross-batch CPV/SPC trending | CPV-Auto, Mareana | Phase 5+ (Section 15) |
| 11 | Structured explanation trace | PwC, Aizon | Per-finding reasoning trace (Section 16) |
| 12 | No-training-on-client-data | CPV-Auto | Documented policy (Section 1.7) |

### 3.3 What Competitors Do Well

**Mareana's architectural anti-hallucination:** Knowledge graph constrains AI to synthesize only from validated, connected data. Clyira's `AntiHallucinationGate` validates after generation; a knowledge graph prevents at the source.

**Acodis's IDP separation:** IDP as a foundation layer that goes beyond OCR to layout analysis, table detection, field classification, and semantic grouping BEFORE compliance logic runs.

**Aizon's process-aware monitoring:** Process context matters when reviewing CPP values. Clyira's L5 checks should understand process context, not just compare numbers.

**A&M's quantified ROI:** 40% cycle time reduction is the benchmark Clyira should target and measure.

### 3.4 Where Competitors Fall Short (Clyira's Opportunity)

- No lot-level cross-document view or evidence completeness checking
- Weak or absent enforcement intelligence (no 483/warning letter matching)
- Binary disposition (pass/fail) rather than nuanced readiness assessment
- No longitudinal analysis across batches for same product
- Single-sector focus (pharma only) with no modular pack architecture

---

## 4. User Roles (Updated in v2.1)

### 4.1 Roles and Permissions

| Role | Permissions | Description |
|---|---|---|
| QA Reviewer | Upload records, create dossiers, review findings, confirm/dismiss findings, mark human-verified, generate review memo | Primary user. Reviews production records and makes finding-level decisions. |
| QA Approver | All Reviewer permissions + assess disposition readiness, sign off on review report | Senior QA who makes the final disposition decision. |
| Manufacturing Reviewer | View dossier (read-only), respond to manufacturing-related findings | Manufacturing SME consulted for production-related findings. |
| QC Reviewer | Upload QC results/COAs, link QC data to dossier, respond to QC-related findings | Lab personnel who provide analytical data. |
| Admin | Configure review settings, manage templates, define CPP/IPC ranges, set Layer 0 defaults | Company administrator who configures the module. |
| Sponsor QA (NEW in v2.1) | View CDMO-prepared dossier, add sponsor comments, approve/reject sponsor package | For CDMO scenarios: the sponsor's QA reviewer who reviews the CDMO's batch package. See Section 17. |

### 4.2 Implementation Note

No new database model is needed for roles. The existing `User.roles` JSONB field supports arbitrary role assignments. Permissions are enforced at the router level via FastAPI dependency injection, consistent with existing Clyira patterns.

---

## 5. Core User Workflow (Updated in v2.1)

### 5.1 End-to-End Workflow

**Step 1: Create Batch Dossier + Layer 0 Classification**
QA Reviewer creates a new BatchDossier, entering lot number, product, and manufacturing date. They also classify the record: product type, sterility, manufacturing context (internal vs. CDMO), and batch purpose (commercial, validation, exhibit, etc.). This classification determines which review packs activate.

**Step 2: Upload Production Record**
QA Reviewer uploads the executed production record (BPR, DHR, or equivalent). The document goes through Clyira's pipeline: text extraction → IDP Engine → section identification → auto-classification → DTAP assignment based on Layer 0 classification.

**Step 3: Attach Supporting Documents**
QA Reviewer (or other roles) attach related documents to the dossier: deviation reports, CAPAs, QC test results, COAs, environmental monitoring records, equipment logs, etc. Each document is assessed individually through its own DTAP.

**Step 4: Evidence Package Completeness Check (NEW in v2.1)**
Before full assessment runs, the system checks: based on the Layer 0 classification, is the evidence set complete? A pharma BPR dossier for a sterile injectable should contain: executed BPR, deviation reports (if any referenced), QC/COA results, environmental monitoring data, filter integrity test results, and sterilization records. The system identifies what's expected vs. what's uploaded and flags gaps.

Evidence completeness is a pre-assessment gate. The dossier can proceed to assessment with gaps, but the evidence completeness status is visible on the dashboard and factors into disposition readiness.

**Step 5: Run Assessment**
Triggering assessment runs the full L1-L11 pipeline with review packs activated by the Layer 0 classification:
- Core Pack checks run for all record types
- Sector Pack checks run based on classification (e.g., Pharma Drug Product Pack + Sterile/Aseptic Pack)
- Each finding is tagged with a verification state: Green, Red, Blue, or Gray

**Step 6: Dossier-Level Aggregation (Micro-batching)**
After individual documents are assessed, the BatchDispositionService computes:
- Composite lot readiness score (weighted aggregate of individual scores)
- Release gate status: evidence completeness, open deviations, open CAPAs, QC pass/fail, data integrity holds
- Cross-document findings: mismatches between documents, missing references
- Cross-document conflict detection: auto-flag when key parameters (yield, dates, lot numbers) differ between dossier documents (see Section 22.2)
- Micro-batching: readiness score recalculates every time a linked document's assessment completes

**Step 7: Human Review (4-State Verification)**
QA Reviewer sees the dossier dashboard with findings classified by verification state:
- **Green:** Rule-verified pass. Reviewer can skip unless they disagree.
- **Red:** Rule-verified fail. Requires reviewer action.
- **Blue:** AI-assisted finding with confidence score. Requires human judgment.
- **Gray:** Unverified — system could not determine a result (OCR failure, missing data, unreadable field). Requires human input.

**Step 8: Disposition Readiness Assessment (Reframed in v2.1)**
Once all findings are addressed, the system presents a disposition readiness status:
- **Ready for QA disposition review:** All gates pass, all critical/high findings addressed, evidence package complete
- **Conditional readiness:** Minor open items with documented justification
- **Not ready:** Major evidence gaps or unresolved critical findings
- **Hold for human QA evaluation:** Fundamental quality or data integrity concerns flagged

The QA Approver reviews the readiness assessment and makes their disposition decision (Release / Conditional Release / Hold / Reject). This is entirely a human decision. Clyira presents evidence and readiness status; humans decide.

**Step 9: Export Review Report**
Generate an audit-ready review report: evidence completeness summary, finding list with 4-state verification classification, reviewer actions and rationale, disposition readiness status and human disposition decision, all evidence-linked to source pages, Part 11-compliant signatures and timestamps.

---

## 6. Processing Pipeline (Updated in v2.1)

### 6.1 What Exists Today

| Stage | Exists? | Implementation |
|---|---|---|
| Document upload + storage | YES | `DocumentService.upload_document()` |
| PDF text extraction | YES | pdfplumber (primary), PyPDF2 (fallback) |
| DOCX text extraction | YES | python-docx library |
| Table extraction from PDF | YES | pdfplumber `extract_tables()` |
| Section identification | YES | Heuristic parser in `_identify_sections()` |
| Auto-classification | YES (needs additions) | `_auto_classify()` — missing MBR/BPR patterns |
| DTAP resolution | YES | `DTAPRegistry.resolve()` |
| Rule engine | YES | `RuleEngine.run()` |
| LLM engine | YES | `LLMEngine.run()` with Groq/Gemini |
| Enforcement matching | YES | `EnforcementEngine.run()` |
| Anti-hallucination | YES | `AntiHallucinationGate.validate()` |
| Scoring | YES | `ScoringEngine.calculate()` |
| Remediation generation | YES | `LLMEngine.generate_remediation()` |
| Finding persistence | YES | `AssessmentService._store_findings()` |
| Audit trail | YES | `Audit` model |
| Tamper-evident hashing | YES | `compute_hash()` |

### 6.2 What Needs to Be Added

| Stage | Status | Phase |
|---|---|---|
| Layer 0 sector routing | NOT BUILT | Phase 1 |
| Auto-classification for MBR/BPR/DHR | GAP | Phase 1 |
| DTAP-007 review (already built, needs validation) | NEEDS REVIEW | Phase 1 |
| Evidence package completeness gate | NOT BUILT | Phase 2 |
| IDP Engine (provider-agnostic) | NOT BUILT | Phase 3 |
| OCR/ICR/IWR | NOT BUILT | Phase 4 |
| Batch Dossier model | NOT BUILT | Phase 2 |
| Batch Disposition Service | NOT BUILT | Phase 2 |
| 4-state finding verification | NOT BUILT | Phase 1 |
| Disposition readiness model | NOT BUILT | Phase 2 |
| Modular review pack composition | NOT BUILT | Phase 1-2 |
| Structured explanation traces | NOT BUILT | Phase 3 |
| Cross-batch CPV/SPC trending | NOT BUILT | Phase 5+ |

### 6.3 Full Vision Pipeline

1. **Intake** — Upload executed production record + supporting documents to BatchDossier
2. **Layer 0 Classification (NEW)** — Product type, sterility, context, batch purpose → determines review pack composition
3. **Evidence Package Completeness (NEW)** — Check uploaded documents against expected evidence set for this product/process type
4. **Preprocessing** — [FUTURE] Page segmentation, scan quality scoring, blank/duplicate page detection
5. **IDP Engine** — Provider-agnostic extraction: layout analysis, table detection, field classification, per-field confidence. See Section 7.
6. **OCR/ICR/IWR** — [FUTURE Phase 4] Three-tier recognition for scanned/handwritten content. See Section 8.
7. **Section Classification** — Existing `_identify_sections()` enhanced with IDP-informed boundaries
8. **Deterministic Rule Engine** — Core Pack + Sector Pack checks → Green/Red findings
9. **AI Co-QA Reasoning** — LLM for semantic analysis (L3, L6, L8) → Blue findings
10. **Unresolvable Detection** — Fields/checks that couldn't be evaluated → Gray findings
11. **Enforcement Matching** — Existing `EnforcementEngine` for L9
12. **Dossier Aggregation** — Cross-document analysis with micro-batching
13. **Anti-Hallucination Validation** — Existing gate + [FUTURE] knowledge graph constraint
14. **Explainability Layer** — Structured explanation trace per finding (Section 16)
15. **Human Verification** — 4-state review workflow
16. **Disposition Readiness** — Readiness status computation (Section 13)
17. **Report Generation** — Audit-ready review report
18. **Feedback/Learning** — [FUTURE] Reviewer corrections stored for tenant-scoped improvement
19. **CPV/SPC Trending** — [FUTURE Phase 5+] Cross-batch statistical trending

---

## 7. IDP Engine Architecture (Updated in v2.1 — Provider-Agnostic)

### 7.1 Why a Separate IDP Layer

Clyira currently goes directly from raw text extraction (pdfplumber) to assessment. This works for well-structured documents but is insufficient for production records, which contain complex tables, mixed content types, hierarchical sections, and spatial field-value relationships.

IDP (Intelligent Document Processing) is a separate concern from assessment. Extraction answers "what does this document contain?" Assessment answers "does this document comply?" Mixing them produces worse results at both.

### 7.2 Provider-Agnostic Design (Updated in v2.1)

Clyira's moat is QA review logic, not extraction. The IDP Engine should be a Clyira orchestration layer with a pluggable extraction backend:

```
IDP Engine (Clyira's orchestration)
├── Provider interface (abstract)
│   ├── AWS Textract adapter
│   ├── Google Document AI adapter
│   ├── Azure AI Document Intelligence adapter
│   ├── ABBYY adapter
│   ├── Open-source adapter (DocTR, Docling, LlamaParse)
│   └── pdfplumber adapter (existing, for digital PDFs)
├── Table recognition orchestrator
├── Field classification logic
├── Confidence normalization (normalize provider-specific scores to 0-1)
└── IDPOutput schema (standardized regardless of provider)
```

**Phase 1-2:** Use existing pdfplumber extraction enhanced with page-boundary preservation. No external IDP provider needed for digital PDFs.

**Phase 3:** Integrate one external provider (likely Azure AI Document Intelligence or Google Document AI based on pharma customer preferences and compliance posture). The adapter normalizes provider output to Clyira's `IDPOutput` schema.

**Phase 4+:** Add OCR/ICR/IWR capabilities via provider or specialized models.

### 7.3 IDPOutput Schema

The IDP Engine produces a standardized structured representation stored in `Document.extracted_sections` (JSONB):

```
IDPOutput:
├── pages[]:
│   ├── page_number: Integer
│   ├── page_type: String [form, narrative, table, signature, blank]
│   ├── regions[]:
│   │   ├── type: String [text, table, handwriting, signature, stamp, checkbox]
│   │   ├── bounding_box: [x0, y0, x1, y1]
│   │   ├── content: String
│   │   ├── confidence: Float (0-1, normalized)
│   │   └── recognition_method: String [digital, ocr, icr, iwr, manual]
│   └── tables[]:
│       ├── headers: String[]
│       ├── rows: String[][]
│       ├── confidence: Float
│       └── table_type: String [ipc_results, material_list, yield_calc, equipment_log, other]
├── fields[]:
│   ├── field_name: String
│   ├── field_value: String
│   ├── source_page: Integer
│   ├── confidence: Float
│   ├── recognition_method: String
│   ├── criticality: String [critical, high, medium, low] (from Field Criticality Model)
│   └── requires_human_verification: Boolean
├── sections[]:
│   ├── title: String
│   ├── start_page: Integer
│   ├── end_page: Integer
│   └── content_summary: String
└── metadata:
    ├── total_pages: Integer
    ├── document_type_detected: String
    ├── scan_quality_score: Float (nullable)
    ├── handwriting_detected: Boolean
    ├── table_count: Integer
    ├── blank_page_indices: Integer[]
    └── idp_provider: String
```

### 7.4 Complex Table Extraction

Production records are full of tables (IPC results, material dispensing, yield calculations, EM data). The IDP Engine must:
- Detect table boundaries per page
- Classify table type
- Extract headers and rows into structured arrays
- Assign per-cell confidence
- Handle multi-page table continuation
- Flag low-confidence cells for human verification

---

## 8. Handwriting and Scan Strategy

### 8.1 Current State

**Can do today:** Extract text from digitally-generated PDFs using pdfplumber.

**Cannot do today:** OCR on scans, handwriting recognition, scan quality assessment, page boundary detection.

### 8.2 Honest Assessment

Handwriting recognition in pharmaceutical production records is an unsolved problem at production quality. No vendor claims perfect handwriting recognition. Acodis reports ">95% accuracy depending on input quality" with human-in-the-loop verification.

### 8.3 Three-Tier Recognition Pipeline

**Tier 1: OCR (Optical Character Recognition)** — Printed/typed text. 98-99% accuracy for clean scans. Phase 4.

**Tier 2: ICR (Intelligent Character Recognition)** — Individual handwritten characters (digits, initials, dates). 90-95% accuracy. Phase 4.

**Tier 3: IWR (Intelligent Word Recognition)** — Handwritten words/phrases using language context and pharmaceutical vocabulary. 80-90% for common terms. Phase 4+.

### 8.4 Phased Rollout

**Phase 1-2:** No OCR. Digital PDFs and eBR exports only. Manual value entry for paper records.

**Phase 3:** IDP Engine with provider-based extraction for digital PDFs. Page boundary preservation.

**Phase 4:** OCR (Tier 1) for printed text in scans. ICR (Tier 2) for handwritten numerics. Confidence gating with human verification.

**Phase 4+:** IWR (Tier 3) for contextual handwritten words. Pharmaceutical vocabulary constraints.

### 8.5 Key Principles

- Never present a recognition-extracted value as ground truth. Always show confidence and source image.
- Dual confidence: extraction confidence (how well the engine read it) vs. finding confidence (how confident the assessment is about compliance).
- Critical parameters (CPPs, IPCs, yields) extracted via any recognition tier MUST be human-verified.
- Store every reviewer correction as tenant-scoped training data.
- Link every extracted value to source page and bounding box.
- No-training-on-client-data: corrections improve extraction within the client's tenant only.

---

## 9. Modular Review Packs (NEW in v2.1 — replaces monolithic rule section)

### 9.1 Architecture

Review packs replace the monolithic DTAP-007 rule set from v1/v2. Each pack is a composable set of checks at specific L1-L11 levels. Packs are additive — the Core Pack always runs, and sector packs layer on top based on Layer 0 classification.

Each pack is implemented as a DTAP overlay. The existing `DTAPRegistry.resolve()` method composes multiple overlays into a single assessment profile.

### 9.2 Core Production Record Pack (All Sectors)

This pack runs for every production record regardless of sector. It covers universal GMP/GDP requirements:

**L1 — Structural Completeness (Rule Engine → Green/Red)**
- Required sections present (product-specific list determined by sector pack)
- Product/lot identification complete
- Batch/lot number format validation
- Manufacturing and expiry/retest dates present
- Page numbering sequential (if detectable)

**L2 — Document Control (Rule Engine → Green/Red)**
- Executed record references approved master record version
- Operator/performer identification on critical steps
- QA/QC reviewer signature present
- Supervisory approval documented where required
- Dual verification where required

**L4 — Data Integrity / ALCOA+ (Hybrid → Red for rule violations, Blue for AI-detected)**
- Corrections use single-line strikethrough with initials and date
- No blank required fields
- Timestamps in logical sequence (no backdating)
- Duplicate data detection
- No pre-signed blank pages
- Contemporaneous recording indicators
- Attributable entries

**L7 — Lifecycle / Timeliness (Rule Engine → Green/Red)**
- Review completed within defined timeframe
- All referenced deviations closed
- No open action items at time of review

**L9 — Enforcement Pattern Matching (Existing Engine → Red)**
- Match findings against FDA 483 observations and warning letters
- Severity elevation for consent decree triggers

**L10 — Longitudinal Analysis (Existing Engine → Blue)**
- Compare record quality across lots for same product
- Detect recurring findings
- Department and operator trending

**L11 — Inspectability (Rule Engine → Green/Red)**
- No TBD placeholders or draft language
- All pages accounted for
- Internal consistency (lot number matches throughout)
- Version control complete

### 9.3 Pharma Drug Product Pack

Activates for: Pharma BMR/BPR, Biologics (combined with Biologics Pack)

**L1 additions:**
- Bill of Materials section present
- Equipment list present
- Processing steps present
- IPC section present
- Yield calculations present
- Packaging section present

**L3 — Content Quality (Hybrid → Blue)**
- Processing steps sufficiently detailed
- IPC descriptions adequate
- Yield calculation methodology clear
- Deviation narrative completeness
- Environmental monitoring referenced
- Equipment cleaning status documented

**L5 — Data Intelligence (Hybrid → Blue)**
- CPP values within specified ranges
- IPC results within acceptance criteria
- Yield within expected range (typically 90-110% of theoretical)
- Material balance calculations correct
- Environmental monitoring within limits

**L6 — Cross-Reference Traceability (LLM, Dossier-Enhanced → Blue)**
- Deviation references match actual deviation documents in dossier
- CAPA references traceable
- Equipment IDs match equipment logs
- Raw material lot numbers traceable to COAs
- Cleaning validation references current

**L8 — Regulatory Compliance (LLM with RAG → Blue)**
- 21 CFR 211.186 (MBR requirements)
- 21 CFR 211.188 (BPR requirements)
- 21 CFR 211.192 (production record review)
- 21 CFR Part 11 if applicable
- EU GMP Chapter 4 / Annex 11 if applicable
- ICH Q10 alignment
- Multi-market: if `target_markets` on dossier includes EMA, PMDA, TGA etc., run parallel checks against those frameworks and tag findings to the specific regulation (see Section 22.1)

### 9.4 Sterile / Aseptic Pack

Activates when: sterility = true

**L5 additions:**
- Environmental monitoring excursion linkage
- Intervention log completeness
- Filter integrity test results (pre/post-use)
- Sterilization cycle evidence
- Aseptic hold-time compliance
- Media fill / process simulation reference (if applicable)
- Endotoxin/bioburden/sterility test linkage
- Container closure integrity evidence
- Visual inspection reconciliation
- Fill weight/volume checks

**L6 additions:**
- EM data cross-referenced with manufacturing dates/times
- Personnel gowning qualification current
- Room classification verification

### 9.5 API Manufacturing Pack

Activates for: API batch records

**L5 additions:**
- Reaction parameters within ranges
- Intermediate testing results
- Solvent usage and recovery tracking
- Impurity profile monitoring
- Reprocessing/reworking documentation (if applicable)

**L8 — Regulatory (replaces pharma references with):**
- ICH Q7 (API GMP) as primary reference
- 21 CFR 211 where applicable
- EU GMP Part II

### 9.6 Biologics Pack

Activates for: Biologics/vaccine batch records

**L5 additions:**
- Cell bank/seed lot traceability
- Bioreactor run parameters
- Harvest pool documentation
- Column chromatography step verification (column ID, resin cycle count)
- Viral clearance/inactivation evidence
- Hold time compliance
- Temperature excursion documentation
- Protein concentration / potency / identity results
- Pooling/fraction decisions documented
- Resin reuse / cleaning linkage

**L6 additions:**
- Bioburden/endotoxin cross-reference
- Comparability protocol reference (if process change)

**L8 additions:**
- ICH Q5 (Quality of Biotechnological Products)
- ICH Q6B (Specifications for Biotechnological Products)

### 9.7 Device DHR Pack (Future — Phase 3+)

Activates for: Medical device DHRs

**L1 additions:**
- DMR (Device Master Record) reference present
- UDI / lot / serial number traceability
- Acceptance records present
- Labeling/IFU version documented

**L5 additions:**
- Process validation evidence referenced
- Dimensional/functional test results
- Sterilization evidence (if sterile device)
- Final inspection/release record

**L6 additions:**
- DMR-to-DHR alignment verification
- Nonconformance linkage
- Rework/repair records (if applicable)

**L8 — Regulatory:**
- 21 CFR 820.184 (DHR requirements)
- 21 CFR 820.90 (Nonconforming product)
- If combination product: + 21 CFR 211 drug GMP

### 9.8 Dietary Supplement Pack (Future — Phase 3+)

Activates for: Dietary supplement BPR/MMR

**L1 additions:**
- Component verification documentation
- Label reconciliation
- Packaging/label controls

**L5 additions:**
- Dietary ingredient identity testing results
- Specifications met for finished product

**L8 — Regulatory:**
- 21 CFR 111.255 (batch production record requirement)
- 21 CFR 111.260 (batch record contents)
- 21 CFR 111.70 (component verification)

### 9.9 Cell Therapy COI/COC Pack (Future — Phase 4+)

Activates for: Cell/gene therapy records

**L1 additions:**
- Chain-of-identity (COI) documentation complete
- Chain-of-custody (COC) documentation complete
- Donor/patient linkage verified
- Material receipt acceptance documented

**L5 additions:**
- Viability and cell count results
- Transduction/editing efficiency
- Cryostorage temperature history
- Shipping temperature verification
- Potency assay results

**L6 additions:**
- Patient/donor ID consistency across all documents
- COI/COC break detection
- Clinical site linkage

**L8 — Regulatory:**
- 21 CFR 1271 (HCT/P requirements)
- Applicable FDA guidance for CGT

### 9.10 CDMO Sponsor Oversight Pack

See Section 17 for full design.

### 9.11 Review Pack Implementation

Each review pack maps to a DTAP overlay file:

| Pack | DTAP File | Phase |
|---|---|---|
| Core Production Record | `app/dtap/packs/core_production.py` | Phase 1 |
| Pharma Drug Product | `app/dtap/packs/pharma_drug_product.py` | Phase 1 |
| Sterile / Aseptic | `app/dtap/packs/sterile_aseptic.py` | Phase 2 |
| API Manufacturing | `app/dtap/packs/api_manufacturing.py` | Phase 3 |
| Biologics | `app/dtap/packs/biologics.py` | Phase 3 |
| Device DHR | `app/dtap/packs/device_dhr.py` | Phase 3+ |
| Dietary Supplement | `app/dtap/packs/dietary_supplement.py` | Phase 3+ |
| Cell Therapy COI/COC | `app/dtap/packs/cell_therapy.py` | Phase 4+ |
| CDMO Sponsor Oversight | `app/dtap/packs/cdmo_sponsor.py` | Phase 2 |

---

## 10. Field Criticality Model (NEW in v2.1)

### 10.1 Why Field Criticality Matters

Not all fields in a production record carry equal risk. A missing operator initial on a non-critical step is not the same as an unreadable CPP value. The field criticality model assigns a criticality level to each field, which drives:
- Human verification requirements (critical fields always need human verification after OCR/ICR)
- Finding severity weighting (a data integrity issue on a critical field is more severe)
- Review workflow (critical-field Gray findings must be resolved before disposition)

### 10.2 Criticality Levels

| Criticality | Examples | Human Verification After OCR | Finding Severity Impact |
|---|---|---|---|
| **Critical** | CPP values, CQA results, sterility results, identity test, chain-of-custody, final disposition signature, yield calculation, patient/donor ID | Always required | Issues auto-elevated to Critical/High severity |
| **High** | IPC results, yield at stages, deviation linkage, QC release results, material lot numbers, equipment IDs | Required unless extraction confidence > 95% | Issues default to High severity |
| **Medium** | Operator signatures/dates, line clearance, equipment cleaning status, environmental monitoring reference | Risk-based (configurable threshold) | Issues default to Medium severity |
| **Low** | Formatting, pagination, non-critical admin fields, header/footer consistency | Sampling-based audit | Issues default to Low severity |

### 10.3 Configuration

Field criticality is defined per review pack. Each pack specifies which fields are critical, high, medium, or low for that sector/product type. The Admin role can override criticality at the company level (e.g., a company may elevate "line clearance" from Medium to High based on their quality system requirements).

Criticality assignments are stored in the DTAP profile and flow through the IDP Engine (which tags each extracted field with its criticality) into the assessment (which uses criticality for severity determination and verification requirements).

---

## 11. Finding Model (Updated in v2.1)

### 11.1 Existing Finding Model

Clyira's `Finding` model in `app/models/assessment.py` already includes: level, severity, category, title, description, evidence, location, regulatory_citation, enforcement_match, suggestion_draft, status, confidence_score, validated, and more. See v2 Section 9.1 for the full field list.

### 11.2 What ChatGPT Proposed vs. What Exists

A separate `MBRFinding` model is NOT needed. The existing Finding model covers all required fields. Creating parallel models fragments data and breaks cross-document analysis.

### 11.3 New Fields for v2.1

Added to the existing Finding model (nullable columns, backward-compatible):

| Field | Type | Description | Phase |
|---|---|---|---|
| **source_page** | Integer, nullable | Page number where finding was detected | Phase 1 |
| **human_verification_required** | Boolean, default False | OCR confidence below threshold or critical field | Phase 1 |
| **verification_state** | String, nullable | "green", "red", "blue", "gray" — 4-state verification | Phase 1 |
| **extraction_confidence** | Float, nullable | How well IDP/OCR read the underlying value (0-1). Distinct from `confidence_score` (assessment confidence). | Phase 3 |
| **explanation_trace** | JSONB, nullable | Structured reasoning trace — rule inputs/thresholds for Green/Red; evidence passages + reasoning for Blue. See Section 16. | Phase 3 |
| **field_criticality** | String, nullable | "critical", "high", "medium", "low" — from Field Criticality Model | Phase 1 |

### 11.4 4-State Verification Model (Updated from v2's 3-color)

| State | Color | Source | Meaning | Reviewer Action |
|---|---|---|---|---|
| **Verified Pass** | Green | Rule engine deterministic pass | Check ran, criterion met | Minimal — review only if disagree |
| **Verified Fail** | Red | Rule engine deterministic fail | Check ran, criterion NOT met | Must address: confirm, dismiss with rationale, or correct |
| **AI-Assisted** | Blue | LLM semantic assessment | AI finding with confidence score | Must review: confirm or reject with reason |
| **Unverified** | Gray | System could not determine | OCR failed, field unreadable, data missing, check could not execute | Must provide human input — enter value, verify from source, or mark as not applicable |

Gray is critical for honesty. When the system can't read a handwritten value, or a section is missing so a check can't run, the finding should say "I couldn't determine this" rather than guessing or silently skipping it.

---

## 12. Human Review Controls (Updated in v2.1)

### 12.1 Existing Review Workflow

Finding status workflow: open → acknowledged → in_progress → resolved → disputed. Scoring engine respects these: resolved = 0x deduction, in_progress = 0.5x, open/disputed = 1.0x.

### 12.2 Review Controls

**Dismiss-all prevention:** No "dismiss all" button. Each finding individually addressed.

**Critical finding escalation:** Critical/High findings require rationale ≥ 50 characters to dismiss. Dismissals trigger QA Approver notification.

**Human verification queue:** Findings with `human_verification_required = True` must be resolved before disposition.

**Gray finding resolution:** Gray findings MUST be resolved before disposition readiness can reach "Ready." The reviewer provides the missing value, verifies from the source document, or marks as "not applicable" with rationale.

**SME assignment:** Findings assigned to Manufacturing Reviewer, QC Reviewer, etc.

**Escalation:** Any reviewer can escalate to QA Approver.

**Correction workflow:** Reviewer corrections stored as `FeedbackCorrection` records — original value, corrected value, finding ID, source coordinates. Tenant-scoped training data.

### 12.3 4-State Review Workflow

**Green finding review:** Compact card with green badge. Auto-acknowledged after reviewer views dossier. Override available if reviewer disagrees.

**Red finding review:** Red badge, specific rule failure, expected vs. observed. Must confirm, dismiss with rationale, or correct data.

**Blue finding review:** Blue badge with confidence score and explanation trace. Evidence passages and reasoning visible. Must confirm or reject.

**Gray finding review:** Gray badge with "human input required" message. Shows source page image (if available). Reviewer enters the correct value, verifies from source, or marks N/A. Gray → resolved or Gray → new Red/Green finding once data is provided.

### 12.4 Shadow / Parallel Review Mode

Before production deployment, AI assessment runs in parallel with human review:
- Reviewer completes review normally (without Clyira)
- Clyira runs assessment on same record
- Results compared: what AI caught vs. what human caught vs. overlap vs. false positives
- Shadow mode = configuration flag on dossier or company settings
- Satisfies GAMP 5 Performance Qualification requirement
- Provides quantitative calibration data before go-live

---

## 13. Disposition Readiness Model (Updated in v2.1)

### 13.1 Reframing: Readiness, Not Recommendation

v2 used "disposition recommendation" — the system would recommend Release/Conditional/Hold/Reject. v2.1 reframes this as "disposition readiness status." The system assesses whether the evidence is complete and the findings are addressed. It does not tell the human what to decide.

This distinction matters for compliance positioning and the Purolea precedent. Clyira reports readiness; humans decide disposition.

### 13.2 Readiness Status Levels

| Status | Meaning | Visual |
|---|---|---|
| **Ready for QA disposition review** | All gates pass, all critical/high findings addressed, evidence package complete, no Gray findings unresolved | Green banner |
| **Conditional readiness** | Minor open items (low/medium findings) with documented justification, or evidence package has optional gaps | Amber banner |
| **Not ready** | Major evidence gaps, unresolved critical findings, or unresolved Gray findings on critical fields | Red banner |
| **Hold for human QA evaluation** | Data integrity concerns flagged, or system detected fundamental quality issues | Red banner with hold icon |

### 13.3 Readiness Computation

**Automatic gates (binary — any failure blocks "Ready"):**
- Data integrity hold on any dossier document → Not Ready
- Unresolved Critical findings → Not Ready
- Unresolved Gray findings on Critical-criticality fields → Not Ready
- Open deviations without closure → Not Ready
- Evidence package missing required document types → Not Ready

**Score-based readiness:**
- Composite dossier score ≥ 90 + all gates pass → Ready
- Score 80-89 + gates pass with minor items → Conditional readiness
- Score 65-79 → Not ready
- Score < 65 → Hold for human QA evaluation

### 13.4 Human Disposition Decision

When the QA Approver reviews the readiness assessment, they make a disposition decision from:
- **Release** — Batch approved for distribution
- **Conditional Release** — Approved with documented conditions (requires risk assessment ≥ 100 chars, conditions list, timeline, responsible person, follow-up date)
- **Hold** — Pending investigation or additional data
- **Reject** — Fundamental quality failure

The system records the readiness status AND the human decision. If the human disposition differs from readiness status (e.g., approver releases despite "Conditional readiness"), the divergence is logged with mandatory rationale and visible in the audit trail.

---

## 14. Knowledge Graph Consideration

### 14.1 Mareana's Approach

Mareana builds a "batch genealogy" knowledge graph connecting materials, equipment, operators, process parameters, deviations, CAPAs, and batches. Their AI (GraphRAG) can only synthesize from validated nodes/edges — architectural anti-hallucination.

### 14.2 Clyira's Path

**Phase 1-2 (MVP):** The Batch Dossier IS a lightweight graph — lot linked to documents. L6 cross-reference checks operate on dossier-linked documents.

**Phase 3:** Entity extraction — raw material lots, equipment IDs, operator names stored as structured entities. Cross-document entity matching within dossiers.

**Phase 5+:** Formal knowledge graph (graph layer on PostgreSQL or Neo4j). GraphRAG for L6/L8 — LLM constrained to validated graph data.

### 14.3 Core Principle (Applies Now)

Even without a formal graph, constrain AI to validated data. The LLM's RAG context for assessment includes only dossier-linked documents, the regulatory corpus, and the enforcement database. Never allow the AI to imagine connections or data that doesn't exist in the system.

---

## 15. Cross-Batch CPV/SPC Trending

### 15.1 What It Is

Continued Process Verification (ICH Q8/Q10, FDA Process Validation Stage 3) requires monitoring CPPs and CQAs across batches. SPC charts (control charts, Cpk/Ppk) are standard tools.

### 15.2 Phased Approach

**Phase 1-2:** Extract and store CPP/IPC values from assessed records. Data accumulation.

**Phase 3-4:** No trending yet — insufficient batch data for statistical validity (need 15-30+ batches).

**Phase 5+:** SPC charts, trend detection (Western Electric rules), process capability indices, integration with L10 longitudinal findings. APR/PQR report generation from accumulated data.

---

## 16. Explainability and Auditability (Updated in v2.1)

### 16.1 Why Explainability Is Non-Negotiable

PwC's AI GxP framework and the Purolea warning letter both establish that AI-assisted decisions in regulated contexts must be traceable to specific inputs, reasoning, and evidence.

### 16.2 Structured Explanation Trace (Renamed in v2.1)

v2 used "SHAP-style explainability." This was inaccurate — Clyira is not running SHAP/LIME algorithms on LLM outputs. v2.1 calls this what it is: a **structured explanation trace.**

Each finding's `explanation_trace` JSONB field contains:

**For Green/Red findings (deterministic):**
```json
{
  "type": "deterministic",
  "rule_id": "l4_correction_format",
  "pack": "core_production",
  "input_values": {"correction_text": "5.2 crossed out, 5.3 written beside", "has_initials": false, "has_date": false},
  "threshold": "ALCOA+ requires corrections with single-line strikethrough, initials, and date",
  "result": "FAIL — initials and date not detected alongside correction",
  "regulatory_basis": "21 CFR 211.188(b), ALCOA+ principles",
  "field_criticality": "high"
}
```

**For Blue findings (AI-assisted):**
```json
{
  "type": "ai_assisted",
  "model": "gemini-2.5-flash",
  "model_version": "2025-05-01",
  "confidence": 0.87,
  "evidence_passages": [
    {"page": 12, "text": "Mixing time: 45 minutes", "relevance": "CPP value extracted"},
    {"page": 3, "text": "Mixing time specification: 30-40 minutes", "relevance": "Specification limit"}
  ],
  "reasoning": "Extracted mixing time (45 min) exceeds upper specification limit (40 min). This represents a CPP excursion.",
  "anti_hallucination_check": "PASSED — both values traced to specific document locations",
  "contributing_factors": ["value_out_of_range", "cpp_parameter", "no_deviation_reference"],
  "field_criticality": "critical"
}
```

**For Gray findings (unverified):**
```json
{
  "type": "unverified",
  "reason": "extraction_failure",
  "detail": "Handwritten value on page 15 could not be read. OCR confidence: 0.32. ICR confidence: 0.41. Below threshold (0.70).",
  "source_page": 15,
  "bounding_box": [120, 340, 280, 380],
  "field_criticality": "critical",
  "action_required": "Human must verify this value from the source document image."
}
```

### 16.3 Assessment Provenance Record (NEW in v2.1)

Every assessment is stamped with provenance metadata for GAMP 5 change control:

```json
{
  "assessment_provenance": {
    "dtap_profile_version": "DTAP-007-v1.2",
    "review_packs_applied": ["core_production_v1.0", "pharma_drug_product_v1.0", "sterile_aseptic_v1.0"],
    "rule_engine_hash": "sha256:a1b2c3...",
    "llm_model": "gemini-2.5-flash",
    "llm_prompt_version": "mbr-assessment-v2.1",
    "idp_provider": "pdfplumber",
    "idp_provider_version": "0.10.3",
    "anti_hallucination_gate_version": "v1.0",
    "enforcement_corpus_date": "2026-05-15",
    "assessment_timestamp": "2026-05-28T14:30:00Z"
  }
}
```

This enables an inspector to ask "what exactly reviewed this batch record?" and get a precise answer.

### 16.4 GAMP 5 Validation Alignment

| GAMP 5 Stage | Clyira Equivalent |
|---|---|
| Validation Master Plan | Architecture proposal (this document) + validation protocol |
| Model Development | DTAP profile + review pack design, rule engine implementation, LLM prompt engineering |
| Design Qualification (DQ) | Architecture review, design spec sign-off |
| Installation Qualification (IQ) | Deployment verification, dependency check |
| Operational Qualification (OQ) | Synthetic test library execution (Section 20) |
| Performance Qualification (PQ) | Shadow/parallel review mode (Section 12.4) |
| Continuous Monitoring | L10 longitudinal analysis, finding accuracy tracking, feedback correction rates, performance KPIs |

---

## 17. CDMO & Multi-Sponsor Architecture (NEW in v2.1)

### 17.1 Why CDMOs Need Special Architecture

CDMOs are Clyira's highest-leverage customer type. A single CDMO manufactures for dozens of sponsors simultaneously. Each sponsor has different batch record templates, quality agreement requirements, CPP/IPC specifications, and approval workflows.

### 17.2 Multi-Sponsor Tenant Model

The current `Company` model assumes one company = one tenant. For CDMOs, the architecture needs sub-tenants:

```
Company (CDMO account)
├── Sponsor Program A
│   ├── DTAP overlay (sponsor-specific additional checks)
│   ├── CPP/IPC ranges (per sponsor quality agreement)
│   ├── Evidence package template (what documents the sponsor expects)
│   ├── Review workflow (CDMO internal review → sponsor QA review)
│   └── Batch Dossiers for Sponsor A's lots
├── Sponsor Program B
│   ├── Different DTAP overlay
│   ├── Different CPP/IPC ranges
│   ├── Different evidence package requirements
│   ├── Different review workflow
│   └── Batch Dossiers for Sponsor B's lots
└── CDMO-wide settings
    ├── Default review packs
    ├── CDMO QA roles
    └── Cross-sponsor longitudinal analysis
```

### 17.3 Dual Review Workflow

CDMOs often have two sequential review stages:

**Stage 1 — CDMO Internal Review:**
- CDMO QA Reviewer assesses the batch record
- Findings reviewed and addressed per CDMO procedures
- CDMO QA Approver signs off on internal review

**Stage 2 — Sponsor Review:**
- Sponsor QA receives the dossier (with CDMO's review results)
- Sponsor QA adds their own comments/findings
- Sponsor QA provides final authorization

The BatchDossier needs a `review_stage` field and stage-specific permissions. CDMO users see and edit in Stage 1; Sponsor QA users see and edit in Stage 2 (plus read-only access to Stage 1 results).

### 17.4 Sponsor Package Readiness

Before the dossier is sent to the sponsor, the CDMO needs a "sponsor package completeness" check:
- All documents required by the quality agreement are included
- CDMO internal review is complete
- All critical/high findings addressed
- Review report generated

This is a variant of the evidence package completeness gate, configured per sponsor program.

### 17.5 Implementation Note

The multi-sponsor model is a data model extension (SponsorProgram entity linked to Company). It does not change the assessment pipeline — it changes how DTAPs are resolved (with sponsor overlay) and how permissions are enforced (stage-based access). Detailed design deferred to Phase 2-3.

---

## 18. Data Model Proposal (Updated in v2.1)

### 18.1 New Entities Required

**NOTE: These are proposed interfaces only. No implementation yet.**

#### BatchDossier (Updated in v2.1)

```
BatchDossier
├── id: UUID (PK)
├── company_id: FK → companies
├── sponsor_program_id: FK → sponsor_programs (nullable, for CDMOs) [NEW]
├── created_by: FK → users
├── lot_number: String (unique per company)
├── product_name: String
├── product_code: String (nullable)
├── dosage_form: String (nullable)
├── batch_size: String (nullable)
├── manufacturing_site: String (nullable)
├── manufacturing_date: String (nullable)
├── target_release_date: String (nullable)
│
├── # Layer 0 Classification [NEW in v2.1]
├── record_family: String [pharma_bpr, api_batch, biologics_batch, sterile_batch, device_dhr, supplement_bpr, cell_therapy, blood_plasma, cdmo_package]
├── product_type: String [small_molecule, biologic, vaccine, api, combination, supplement, device, cell_therapy, gene_therapy]
├── is_sterile: Boolean (default False)
├── manufacturing_context: String [internal, cdmo_received]
├── batch_purpose: String [commercial, validation, exhibit, stability, tech_transfer, clinical, scale_up]
├── target_markets: JSONB (nullable) — ["FDA", "EMA", "PMDA", "TGA", "ANVISA", "NMPA"] [NEW — multi-market]
│
├── # Status and Readiness
├── status: String [draft, under_review, pending_disposition, released, conditionally_released, on_hold, rejected, reopened]
├── readiness_status: String (nullable) [ready, conditional, not_ready, hold] [RENAMED in v2.1]
├── readiness_score: Float (nullable) — composite [RENAMED]
├── readiness_band: String (nullable)
│
├── # Human Disposition Decision [REFRAMED in v2.1]
├── disposition_decision: String (nullable) [release, conditional_release, hold, reject]
├── disposition_rationale: Text (nullable)
├── disposition_divergence: Boolean (default False) — True if decision differs from readiness [NEW]
├── conditional_release_conditions: JSONB (nullable)
│
├── # Gates
├── gate_evidence_complete: Boolean (default False) [NEW in v2.1]
├── gate_open_deviations: Boolean (default True)
├── gate_open_capas: Boolean (default True)
├── gate_qc_complete: Boolean (default False)
├── gate_data_integrity: Boolean (default True)
├── gate_all_findings_addressed: Boolean (default False)
├── gate_gray_findings_resolved: Boolean (default False) [NEW in v2.1]
│
├── # Review workflow
├── review_stage: String [cdmo_internal, sponsor_review, complete] (nullable) [NEW]
├── shadow_mode: Boolean (default False)
├── campaign_id: UUID (nullable) — links sequential dossiers in campaign manufacturing [NEW — Section 22.6]
│
├── # Audit
├── released_by: FK → users (nullable)
├── released_at: DateTime (nullable)
├── created_at: DateTime
├── updated_at: DateTime
```

#### EvidencePackageTemplate (NEW in v2.1)

```
EvidencePackageTemplate
├── id: UUID (PK)
├── company_id: FK → companies
├── record_family: String
├── product_type: String (nullable)
├── is_sterile: Boolean (nullable)
├── required_document_roles: JSONB — list of required roles (e.g., ["primary_bpr", "qc_result", "deviation"])
├── optional_document_roles: JSONB — list of optional roles
├── sterile_additional_roles: JSONB (nullable) — added when sterile
├── description: Text (nullable)
├── created_at: DateTime
├── updated_at: DateTime
```

#### BatchDossierDocument (Unchanged from v2)

```
BatchDossierDocument
├── id: UUID (PK)
├── dossier_id: FK → batch_dossiers
├── document_id: FK → documents
├── role: String [primary_bpr, deviation, capa, qc_result, coa, environmental_monitoring, equipment_log, reprocessing_record, sterilization_record, filter_integrity, packaging_record, labeling_record, other]
├── sequence_order: Integer (nullable)
├── notes: Text (nullable)
├── added_by: FK → users
├── added_at: DateTime
```

#### FeedbackCorrection (Updated in v2.1)

```
FeedbackCorrection
├── id: UUID (PK)
├── finding_id: FK → findings
├── document_id: FK → documents
├── corrected_by: FK → users
├── field_name: String
├── original_value: String
├── corrected_value: String
├── source_page: Integer (nullable)
├── bounding_box: JSONB (nullable)
├── extraction_confidence: Float (nullable)
├── recognition_method: String (nullable)
├── field_criticality: String (nullable) [NEW]
├── correction_rationale: Text (nullable)
├── created_at: DateTime
```

#### SponsorProgram (NEW in v2.1)

```
SponsorProgram
├── id: UUID (PK)
├── company_id: FK → companies (the CDMO)
├── sponsor_name: String
├── sponsor_code: String (nullable)
├── dtap_overlay: JSONB (nullable) — sponsor-specific additional checks
├── cpp_ipc_ranges: JSONB (nullable) — sponsor-defined parameter ranges
├── evidence_template_id: FK → evidence_package_templates (nullable)
├── quality_agreement_reference: String (nullable)
├── active: Boolean (default True)
├── created_at: DateTime
├── updated_at: DateTime
```

### 18.2 Existing Entities — Unchanged

Document, Assessment, Finding (with new nullable columns), Company, User, Audit, DocumentReference, EnforcementRecord, RegulatoryCorpus — all unchanged.

### 18.3 Entities NOT Needed

MBRReviewJob, UploadedBatchFile, BatchRecordSection, MBRFinding, ReviewerAction, HumanVerificationItem, ReviewReport, ProcessingAuditLog — all duplicate existing functionality. See v2 Section 15.3 for rationale.

---

## 19. UI Proposal (Updated in v2.1)

### 19.1 New Screens

**Batch Dossiers List** — Table with lot number, product, status, readiness score/band, gate status icons, readiness status, manufacturing date, Layer 0 classification badges. Shadow mode dossiers visually distinct. Filters by status, product, sector, readiness, date range.

**New Batch Dossier** — Form: lot number, product, dates, Layer 0 classification dropdowns (record family, product type, sterility, manufacturing context, batch purpose). Upload primary record and optionally attach supporting documents.

**Dossier Dashboard** — The core screen:
- Header: lot, product, status, readiness score, readiness status vs. human disposition (highlight if divergent)
- Evidence completeness panel: expected documents vs. uploaded, with gaps highlighted
- Gate status panel: green/red/amber icons for each gate
- Finding summary by verification state: Green (X pass), Red (X addressed / Y total), Blue (X confirmed / Y total), Gray (X resolved / Y total)
- Documents panel: cards per linked document
- Findings list: aggregated, grouped by state then severity, filterable
- Timeline: chronological actions
- Disposition panel: for QA Approver — readiness status + 4-tier decision + rationale

**Document Viewer** — Side-by-side: source PDF on left, findings on right. Color-coded finding cards. Extraction confidence indicators. Gray finding resolution interface. Explanation trace expandable on Blue findings.

**Shadow Mode Report** — AI vs. human comparison: alignment metrics, false positives/negatives, threshold tuning recommendations.

**Review Report Export** — Evidence completeness summary, findings with 4-state classification, reviewer actions, readiness status, human disposition, explanation traces, evidence-linked, Part 11 signatures.

### 19.2 Role-Based Dashboard Views (NEW in v2.1)

| Role | Dashboard Focus |
|---|---|
| QA Reviewer | My findings queue, verification queue (Gray findings), assigned findings |
| QA Approver | Dossiers awaiting disposition, escalated findings, release calendar |
| Manufacturing Reviewer | Manufacturing-related findings assigned to me |
| QC Reviewer | QC-related findings, missing QC data alerts |
| Sponsor QA | Dossiers in sponsor review stage, sponsor comment workflow |
| Management/RA | Aggregate metrics, CPV trends, readiness distribution, KPI dashboard |

### 19.3 Performance KPI Dashboard (NEW in v2.1)

Track and display:
- Average time from dossier creation to disposition
- Findings per batch (trending — should decrease over time)
- False positive rate (findings dismissed by reviewers)
- False negative rate (from shadow mode — findings humans caught that AI missed)
- Reviewer throughput (batches per QA person per week)
- Finding state distribution (Green/Red/Blue/Gray ratio — indicates rule coverage)
- Evidence completeness rate (% of dossiers with complete evidence packages)
- Readiness-to-disposition alignment (how often humans agree with readiness status)

---

## 20. Synthetic Test Library (NEW in v2.1)

### 20.1 Why This Is Mandatory

Without test records with known answer keys, Clyira cannot validate its assessment accuracy, calibrate confidence thresholds, demonstrate value to customers, or satisfy GAMP 5 OQ/PQ requirements.

### 20.2 Test Set Design

Each test record is a synthetic or anonymized production record with a known set of findings (the "answer key"). Test sets are organized by sector and scenario:

**Pharma BPR Test Sets:**

| Test ID | Scenario | Expected Findings |
|---|---|---|
| PHARMA-001 | Clean BPR — all fields complete, all values in range | 0 Critical, 0 High, ≤2 Low/Info |
| PHARMA-002 | Missing signatures — 3 unsigned steps | 3 High (L2 document control) |
| PHARMA-003 | Yield mismatch — actual 85% vs. expected 90-110% | 1 Critical (L5 data intelligence) |
| PHARMA-004 | Data integrity violation — correction without initials/date | 1 Critical (L4 ALCOA+) |
| PHARMA-005 | Deviation referenced but not in dossier | 1 High (L6 cross-reference) |
| PHARMA-006 | Missing QC results in dossier | Evidence completeness gate failure |
| PHARMA-007 | Backdated timestamps | 1 Critical (L4 data integrity) |
| PHARMA-008 | Multiple issues — dirty BPR with 5+ findings across levels | Mixed findings, tests composite scoring |
| PHARMA-009 | Poor scan quality (Phase 4) | Multiple Gray findings (unreadable fields) |
| PHARMA-010 | Handwritten values (Phase 4) | Extraction confidence < threshold, human verification required |

**Sterile Scenario Test Sets:**

| Test ID | Scenario |
|---|---|
| STERILE-001 | Clean sterile BPR with EM data |
| STERILE-002 | EM excursion not linked to deviation |
| STERILE-003 | Filter integrity test result missing |
| STERILE-004 | Hold time exceeded without documentation |

**Device DHR Test Sets (Future):**

| Test ID | Scenario |
|---|---|
| DEVICE-001 | Clean DHR with acceptance records |
| DEVICE-002 | UDI/lot traceability gap |
| DEVICE-003 | DMR-DHR version mismatch |

**CDMO Package Test Sets:**

| Test ID | Scenario |
|---|---|
| CDMO-001 | Complete sponsor package |
| CDMO-002 | Sponsor-required document missing |
| CDMO-003 | COA discrepancy vs. BPR values |

### 20.3 Test Execution Protocol

1. Load test record into system
2. Run assessment with known DTAP + review packs
3. Compare findings against answer key
4. Compute precision (correct findings / total findings generated) and recall (correct findings / total expected findings)
5. Track false positives and false negatives
6. Adjust thresholds if precision/recall below target (target: ≥95% recall for Critical findings, ≥90% precision overall)

### 20.4 Seeded Record Testing

Beyond synthetic records, create "seeded" records — real batch record templates with intentionally inserted errors. Used for:
- Customer-specific validation (OQ testing with the customer's actual templates)
- Ongoing regression testing when rules or prompts change
- Shadow mode calibration

---

## 21. Validation Strategy (NEW in v2.1)

### 21.1 Intended Use Statement

Clyira's Batch & Lot Record Review module is intended for use as an AI-assisted review support tool in regulated life science environments. It is designed to help qualified QA professionals identify potential compliance gaps, completeness issues, and data integrity concerns in executed production records. It does NOT make disposition decisions, replace human review, or serve as the sole basis for batch release.

### 21.2 Known Limitations

- AI-assisted findings (Blue) may contain false positives or false negatives. Human review is always required.
- OCR/ICR/IWR extraction is not 100% accurate. Critical values must be human-verified.
- The system cannot detect issues not covered by its review packs.
- Assessment quality depends on document quality — poorly scanned or illegible records will produce Gray findings.
- The system does not have access to external data sources (ERP, LIMS, MES) unless explicitly integrated. Cross-reference checks are limited to documents uploaded to the dossier.

### 21.3 Validation Protocol

**Pre-deployment:**
1. Install and configure Clyira with appropriate review packs
2. Execute synthetic test library (Section 20) — OQ
3. Run shadow mode on ≥ N batches (recommended: 10-20 per product) — PQ
4. Evaluate precision/recall against answer keys and human baseline
5. Document results in Validation Report

**Ongoing:**
- Monitor false positive rate (finding dismissal rate by reviewers)
- Monitor false negative rate (human catches that AI missed — via periodic manual re-review)
- Track assessment provenance (Section 16.3) for change control
- Re-validate after any rule change, prompt update, model change, or IDP provider update
- Periodic performance review (recommended: quarterly)

### 21.4 Change Control

Any change to the following triggers re-validation:
- DTAP profile / review pack rules
- LLM model version or prompt templates
- IDP provider or provider version
- Scoring weights or severity thresholds
- Confidence thresholds for human verification
- Anti-hallucination gate logic

Changes are logged with the assessment provenance record (Section 16.3), enabling traceability from any assessment to the exact system configuration that produced it.

### 21.5 Validation Documentation Clyira Provides

Clyira should provide validation support documentation that customers can use within their own quality systems:

- IQ protocol template (installation verification checklist)
- OQ protocol template (synthetic test execution + expected results)
- PQ protocol template (shadow mode execution + comparison criteria)
- Validation Report template
- Traceability matrix (requirements → design → test → verification)

This is a differentiator — most AI vendors leave validation entirely to the customer.

---

## 22. Additional Design Considerations — Stress Test Gaps (NEW in v2.1)

This section captures 13 additional design considerations identified during cross-scenario stress testing. Each is classified by priority and phase.

### 22.1 Multi-Market Regulatory Compliance

**Gap:** A batch released for the US, EU, and Japan must satisfy different regulatory frameworks simultaneously. A batch may be releasable under FDA rules but not under EMA Annex 11.

**Design:** The BatchDossier gains a `target_markets` field (JSONB array of regulatory agencies). L8 regulatory compliance checks run against ALL applicable frameworks, and findings are tagged with the specific regulation violated. The dossier dashboard shows per-market readiness status.

**Phase:** Phase 2 (add `target_markets` to model). Phase 3 (multi-framework L8 checks).

### 22.2 Cross-Document Conflict Detection

**Gap:** When the BPR says yield was 95% but the QC COA says yield was 88%, the system should auto-detect the discrepancy.

**Design:** The BatchDispositionService includes a conflict detection pass. After all dossier documents are assessed, cross-document value matching runs for key parameters (yield, lot numbers, dates, material quantities). Conflicting values between documents auto-generate a Critical L6 finding with both source documents and values cited.

**Phase:** Phase 2 (basic — lot number and date consistency). Phase 3 (parameter-level matching after IDP Engine extracts structured fields).

### 22.3 Content Hash Deduplication

**Gap:** Nothing prevents the same document from being uploaded to two different dossiers, or uploaded twice to the same dossier.

**Design:** At upload time, compute a content hash (SHA-256 of extracted text). Check against existing documents in the same company. If a match is found:
- Same dossier: block upload with "this document is already in this dossier"
- Different dossier: warn "this document is also linked to dossier [lot number] — is this intentional?" (may be legitimate for shared deviations)

Content hash is already computed for tamper-evident hashing on assessments (`content_hash` field on Assessment model). Extend to documents.

**Phase:** Phase 2.

### 22.4 BPR Versioning Within Dossier

**Gap:** Batch records may be amended after initial completion — a page is replaced, a correction is formally issued. The dossier needs to handle original + amendment.

**Design:** The `BatchDossierDocument` join table gains an optional `supersedes_id` (FK to another BatchDossierDocument). When an amendment is uploaded, it links to the document it supersedes. The assessment runs on the latest version, but the original is preserved for audit trail. A "version history" view on the document card shows all versions.

**Phase:** Phase 3.

### 22.5 Post-Disposition Dossier Amendment

**Gap:** After a dossier is dispositioned (Released), a new deviation may be discovered, or QC results may be invalidated. The dossier needs a reopening workflow.

**Design:** The dossier status includes "reopened." Reopening requires:
- Documented reason (minimum 100 characters)
- Authorized by QA Approver
- Full audit trail entry
- Re-assessment of affected documents
- Re-computation of readiness status
- New disposition decision required

The original disposition and the reopening event are both permanently recorded. A reopened-then-re-released dossier shows both disposition records in its history.

**Phase:** Phase 2 (basic reopening). Phase 3 (automated re-assessment triggers).

### 22.6 Campaign Manufacturing Consideration

**Gap:** Sequential batches of the same product manufactured without cleaning between batches (common for oral solids) are interconnected — Batch N's cleaning record is Batch N+1's starting point, and a deviation in Batch N may affect N+1.

**Design:** A lightweight "campaign" entity linking sequential dossiers for the same product on the same line. When a dossier in a campaign has a Critical finding, other dossiers in the same campaign receive an informational finding noting the potential impact. L10 longitudinal analysis is campaign-aware.

**Phase:** Phase 3+. Not MVP, but the BatchDossier model should include a nullable `campaign_id` field from Phase 2 to avoid migration later.

### 22.7 Partial Assessment Recovery

**Gap:** If the LLM API fails mid-assessment (Groq/Gemini timeout), the assessment is partially complete. The current pipeline may require full re-run.

**Design:** The assessment orchestrator should checkpoint completed checks. On re-run, skip checks that already produced findings and resume from the last incomplete check. The `Assessment` model's existing `status` field (queued → running → completed → failed) supports this. Add a `last_completed_check` field or store check completion status in the JSONB metadata.

**Phase:** Phase 2 (add checkpoint logic to orchestrator).

### 22.8 ERP / LIMS / MES Integration Schemas

**Gap:** Without external data sources, cross-reference checks (L6) are limited to documents in the dossier. Integration with ERP (Bill of Materials), LIMS (QC results), and MES (execution data) would enable richer verification.

**Design:** Define integration interfaces now, build adapters later:

```
ERPIntegration (interface):
├── get_bill_of_materials(product_code, batch_size) → MaterialList
├── get_material_specifications(material_code) → Specifications
└── verify_material_lot(lot_number) → MaterialLot

LIMSIntegration (interface):
├── get_test_results(lot_number) → TestResults[]
├── get_coa(lot_number) → COA
└── get_stability_data(product_code, lot_number) → StabilityData

MESIntegration (interface):
├── get_execution_record(lot_number) → ExecutionData
├── get_equipment_log(equipment_id, date_range) → EquipmentLog
└── get_environmental_data(room_id, date_range) → EnvironmentalData
```

These interfaces are NOT built in the MVP. They define the contract so that when integration is built (Phase 4+), the assessment pipeline already knows what data to expect.

**Phase:** Phase 2 (define interfaces). Phase 4+ (build adapters).

### 22.9 Controlled Substance Overlay

**Gap:** Batch records for DEA Schedule II-V products have additional regulatory requirements: DEA Form 222 reconciliation, strict yield accountability (every milligram), dual-witness destruction/waste documentation, vault inventory reconciliation.

**Design:** A "Controlled Substance Overlay" that activates when the product is flagged as a controlled substance in Layer 0 classification. Additional L5 checks for yield accountability strictness and L6 checks for DEA documentation linkage.

**Phase:** Phase 3+ (add as overlay pack when demand exists).

### 22.10 Combination Product Dual-Framework Assessment

**Gap:** Drug-device combinations (auto-injectors, inhalers, transdermal patches) must satisfy both drug GMP (21 CFR 211) and device QSR (21 CFR 820). L8 checks need dual-framework awareness.

**Design:** When Layer 0 classification indicates "combination product," both the Pharma Drug Product Pack and the Device DHR Pack activate simultaneously. L8 regulatory checks run against both 21 CFR 211 and 21 CFR 820.

**Phase:** Phase 3+ (when Device DHR Pack is built).

### 22.11 Part 11 Electronic Signature Integration

**Gap:** For the review report to be truly audit-ready, it needs compliant e-signatures — not just "user clicked a button." 21 CFR Part 11 requires: meaning of signature, signature (with printed name), date/time, and second signature if signing on behalf of another.

**Design:** The disposition decision and review report sign-off should capture:
- Signer identity (verified via authentication)
- Meaning of signature ("I have reviewed this dossier and approve its disposition as [Release/etc.]")
- Timestamp (server-generated, tamper-evident)
- Additional signature for signing on behalf (rare but required for compliance)

Full Part 11 e-signature may require integration with an external signature service (DocuSign, Adobe Sign) or custom implementation. For MVP, capture the metadata fields; actual cryptographic signing is Phase 3+.

**Phase:** Phase 2 (capture metadata). Phase 3+ (cryptographic signing).

### 22.12 Compounding Pharmacy High-Throughput Mode

**Gap:** 503B outsourcing facilities produce hundreds of small batches per week. Their records are simpler but far more numerous. The standard dossier workflow (create → upload → review → disposition) is too heavyweight.

**Design:** A "high-throughput mode" where:
- Batch dossiers are auto-created from a CSV upload (lot number, product, date, link to record)
- Assessment runs automatically on upload
- Dashboard shows only exceptions (Red/Blue/Gray findings)
- Green-only dossiers can be bulk-acknowledged
- Focus on statistical sampling rather than individual review

**Phase:** Phase 4+ (requires validated assessment accuracy first).

### 22.13 Regulatory Submission Report Generation

**Gap:** For NDA/ANDA/BLA filings, batch records for exhibit batches are part of the regulatory submission. Clyira could generate reports aligned with CTD Module 3.2.P.3.3 (Description of Manufacturing Process and Process Controls).

**Design:** A "regulatory submission export" format that transforms dossier data into CTD-aligned sections. Premium feature for companies in active filing.

**Phase:** Phase 5+ (requires accumulated structured data from IDP Engine).

---

## 23. Phased Implementation (Updated in v2.1)


### Phase 0: Architecture Finalization

**What:** This document (v2.1). Finalize with product owner review. No code.
**Deliverables:** Approved architecture proposal, synthetic test library design, validation protocol templates.
**Duration:** 1-2 weeks for review and alignment.

### Phase 1: Single Pharma BPR Assessment (Quick Win)

**What:**
- Review and validate already-built DTAP-007 against v2.1 review pack structure
- Restructure into Core Pack + Pharma Drug Product Pack
- Fix `_auto_classify()` for MBR/BPR recognition
- Add `verification_state` (Green/Red/Blue/Gray) to Finding model
- Add `field_criticality` to Finding model
- Add `source_page` to Finding model
- Layer 0 classification (manual — dropdown on document upload)
- Execute PHARMA-001 through PHARMA-008 synthetic tests
- End-to-end verification with test documents

**Does not include:** Batch Dossier, IDP Engine, OCR, new UI screens, CDMO features.
**Complexity:** Low (2-3 weeks).
**Value:** Proves the review pack architecture works. Single-document pharma BPR assessment with 4-state findings. Measurable accuracy against test library.

### Phase 2: Batch Dossier MVP

**What:**
- BatchDossier model + migration
- Layer 0 classification on dossier
- Evidence package completeness gate + EvidencePackageTemplate
- BatchDispositionService with readiness model (not recommendation)
- Micro-batching score recalculation
- Dossier API routes
- Dossier UI (list, dashboard, document linking, evidence completeness)
- 4-state finding review workflow
- Disposition readiness + human disposition decision
- FeedbackCorrection model
- Shadow mode infrastructure
- Sterile/Aseptic Review Pack (if customer need)
- CDMO Sponsor Oversight Pack (basic — if customer need)
- Execute CDMO and sterile synthetic tests
- Review report export

**Does not include:** IDP Engine, OCR/handwriting, knowledge graph, CPV trending.
**Complexity:** Medium (5-7 weeks).
**Value:** The differentiated product. Lot-level cross-document review with evidence completeness, 4-state verification, disposition readiness, and shadow mode. No competitor offers this.

### Phase 3: IDP Engine + Explainability

**What:**
- IDP Engine layer (provider-agnostic — start with enhanced pdfplumber, add one external provider)
- Page-boundary preservation
- Complex table extraction
- Per-field confidence scoring (extraction_confidence on Finding)
- Structured explanation traces on all findings
- Assessment provenance records
- Dual confidence scoring in UI
- Biologics Review Pack (if customer need)
- API Manufacturing Review Pack (if customer need)

**Does not include:** OCR/ICR/IWR, knowledge graph, CPV trending.
**Complexity:** Medium-High (4-6 weeks).
**Value:** Dramatically better extraction quality. Explainability satisfies GAMP 5 requirements. Assessment provenance enables full auditability.

### Phase 4: OCR/ICR/IWR + Handwriting

**What:**
- Three-tier recognition pipeline via IDP provider
- OCR for printed text in scans
- ICR for handwritten numerics
- IWR for contextual handwritten words
- Human verification queue in UI
- Scan quality scoring
- Gray finding resolution workflow fully operational
- Device DHR Review Pack (if market demand)
- Dietary Supplement Pack (if market demand)

**Complexity:** High (6-8 weeks).
**Value:** Opens paper-based customer market.

### Phase 5+: CPV/SPC Trending + Knowledge Graph Foundations

**What:** Cross-batch CPV trending, SPC charts, entity extraction for graph foundations, APR/PQR report generation, CDMO multi-sponsor full implementation, Cell Therapy Pack.
**Complexity:** High (8-12 weeks per major feature).
**Value:** Deep competitive moats, regulatory compliance for CPV, long-term platform play.

### Parallel Track: QC Test Record DTAP

Can be built alongside any phase. DTAP-008 for QC test records/COAs. 2-3 weeks. Makes the dossier's QC gate functional.

---

## 24. Risks and Open Questions (Updated in v2.1)

### 24.1 Technical Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Handwriting accuracy | High | Three-tier pipeline, confidence gating, mandatory human verification. Phase 4. |
| Template variability | High | DTAP is template-agnostic (content, not layout). IDP Engine + LLM fallback. |
| Validation burden | High | Shadow mode for PQ. Validation documentation templates. Synthetic test library. |
| False negatives | Medium | Conservative thresholds. Human verification. Shadow mode quantifies rate. |
| LLM cost scaling (100+ page records) | Medium | IDP pre-processing reduces what LLM analyzes. Chunking strategy for large documents. |
| Multi-sector rule complexity | Medium | Modular review packs prevent rule chaos. Each pack independently testable. |
| IDP provider lock-in | Low | Provider-agnostic adapter pattern. Standardized IDPOutput schema. |
| Knowledge graph complexity | High | Deferred to Phase 5+. Lightweight dossier linking sufficient for MVP. |
| Multi-language documents | Medium | Phase 4+ consideration. Language detection in IDP Engine. Multilingual LLM prompts. |
| Large document processing (500+ pages) | Medium | Document segmentation by manufacturing stage. Chunking with cross-chunk references. |

### 24.2 Product Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Reviewer overreliance on AI | High | 4-state verification makes AI findings (Blue) visually distinct. Gray forces human input. Purolea positioning. |
| Confusion with batch release | High | "Readiness" not "recommendation." No "Release Batch" button. Human disposition always required. |
| Scope creep toward MES | Medium | Clear boundary: post-hoc review, not execution. |
| Green-finding rubber-stamping | Medium | Periodic random audit. Shadow mode comparison. Aggregate stats in report. |
| Sector breadth dilution | Medium | Start pharma-only. Add sector packs based on customer demand, not speculation. |
| CDMO pricing complexity | Low | Multi-sponsor adds value but also complexity. Validate with 1-2 CDMO customers first. |

### 24.3 Open Questions for Product Owner

1. **Target customer profile:** Companies with digital eBR exports? Paper-based? Both? Determines IDP/OCR priority.

2. **First sector pack beyond pharma:** Sterile, device, supplement, API, or biologics? Based on pipeline/demand.

3. **CDMO priority:** Build multi-sponsor architecture in Phase 2 or defer to Phase 3?

4. **QC Test Record timing:** Build alongside Phase 2 (stronger dossier value) or separate?

5. **Shadow mode duration:** How many batches before go-live? Industry PQ standard is 3 consecutive batches; AI calibration may need 10-20.

6. **Validation documentation:** Provide IQ/OQ/PQ templates? Significant differentiator but documentation effort.

7. **Pricing model:** Included in subscription or add-on? Per-sector pack pricing?

8. **IDP provider selection:** Azure AI Document Intelligence vs. Google Document AI vs. AWS Textract for Phase 3?

9. **Conditional release workflow:** Integrate with customer change control / CAPA system for condition tracking, or manual tracking for MVP?

10. **APR/PQR generation:** High-value output from accumulated data. Prioritize in Phase 5 or earlier?

11. **Recall investigation workflow:** High-value but specialized. Design now, build when?

12. **Post-disposition dossier reopening:** What workflow when a released batch needs re-evaluation?

---

## 25. Recommendation (Updated in v2.1)

### 25.1 Build Sequence

**Phase 0 → Phase 1 → Phase 2 → Phase 3, with QC Test Record in parallel starting Phase 2.**

### 25.2 Rationale

**Phase 0 (1-2 weeks):** Align on this architecture. Finalize synthetic test library. No code.

**Phase 1 (2-3 weeks):** Validate the assessment pipeline works for a single pharma BPR. Low risk, quick feedback, measurable accuracy. Proves the review pack architecture.

**Phase 2 (5-7 weeks):** Deliver the Batch Dossier MVP with evidence completeness, 4-state verification, disposition readiness, and shadow mode. This is the differentiated product. No competitor offers lot-level cross-document review with evidence completeness gating.

**Phase 3 (4-6 weeks):** IDP Engine + explainability. Makes the product enterprise-defensible and GAMP 5-auditable.

**Total to first shippable product (Phase 1 + Phase 2): 7-10 weeks.**

### 25.3 Why This Sequence

- Competitive research confirms the Batch Dossier with evidence completeness is genuinely unique
- Modular review packs prevent rule chaos as sectors are added
- 4-state verification (Green/Red/Blue/Gray) is more honest than 3-color — Gray forces the system to admit uncertainty
- "Readiness" framing is safer than "recommendation" — critical post-Purolea
- Shadow mode de-risks deployment with quantitative calibration
- Synthetic test library enables measurable quality from day one
- Sector routing architecture means adding device DHR or supplement BPR later is a pack addition, not an architecture change
- CDMO multi-sponsor is a natural Phase 2-3 extension once the core dossier works

### 25.4 The Architecture's Extensibility Thesis

The core architecture (Layer 0 classification → modular review packs → Batch Dossier with evidence completeness → 4-state verification → disposition readiness) works for ANY regulated production record. Pharma BPR, device DHR, supplement BPR, cell therapy COI/COC — the workflow is the same, only the checks differ. Each new sector is a new review pack, not a new architecture.

This is the investor story: platform, not feature. Start with pharma BPR, prove the pattern, then replicate across sectors.

**Final decision should be made by the product owner** based on customer feedback, market timing, and resource availability.

---

## 26. Appendix: Codebase Inventory

### Files That Exist and Are Relevant

| File | Status | Notes |
|---|---|---|
| `app/dtap/profiles/mbr.py` | Built (needs review + restructure into packs) | DTAP-007, 87 checks — to be split into Core + Pharma packs |
| `app/dtap/registry.py` | Modified | MBR registered; needs pack composition logic |
| `app/engines/rule_engine.py` | Modified | 44 MBR checks at end of file; to be reviewed against pack structure |
| `app/services/document_service.py` | Needs modification | `_auto_classify()` missing MBR/BPR/DHR patterns |
| `app/engines/orchestrator.py` | No changes needed | Existing pipeline handles via DTAP |
| `app/engines/scoring.py` | No changes needed | Existing scoring works with DTAP weights |
| `app/engines/enforcement_engine.py` | No changes needed | 211.192 already in corpus |
| `app/engines/validator.py` | No changes needed | Anti-hallucination gate is DTAP-agnostic |
| `app/models/assessment.py` | Needs new nullable columns | verification_state, extraction_confidence, explanation_trace, source_page, human_verification_required, field_criticality |
| `app/models/document.py` | Minor enhancement | extracted_sections JSONB to support IDPOutput |

### Files That Need to Be Created

| File | Purpose | Phase |
|---|---|---|
| `app/dtap/packs/core_production.py` | Core Production Record Pack | Phase 1 |
| `app/dtap/packs/pharma_drug_product.py` | Pharma Drug Product Pack | Phase 1 |
| `app/dtap/packs/sterile_aseptic.py` | Sterile/Aseptic Pack | Phase 2 |
| `app/dtap/packs/cdmo_sponsor.py` | CDMO Sponsor Oversight Pack | Phase 2-3 |
| `app/dtap/packs/biologics.py` | Biologics Pack | Phase 3 |
| `app/dtap/packs/api_manufacturing.py` | API Manufacturing Pack | Phase 3 |
| `app/dtap/packs/device_dhr.py` | Device DHR Pack | Phase 3+ |
| `app/dtap/packs/dietary_supplement.py` | Dietary Supplement Pack | Phase 3+ |
| `app/dtap/packs/cell_therapy.py` | Cell Therapy COI/COC Pack | Phase 4+ |
| `app/models/batch_dossier.py` | BatchDossier + BatchDossierDocument | Phase 2 |
| `app/models/evidence_package_template.py` | EvidencePackageTemplate | Phase 2 |
| `app/models/feedback_correction.py` | FeedbackCorrection | Phase 2 |
| `app/models/sponsor_program.py` | SponsorProgram (CDMO) | Phase 2-3 |
| `app/services/batch_disposition_service.py` | Readiness computation, gates, micro-batching | Phase 2 |
| `app/services/evidence_completeness_service.py` | Evidence package check | Phase 2 |
| `app/services/idp_engine.py` | IDP orchestration + provider adapters | Phase 3 |
| `app/routers/batch_dossiers.py` | Dossier API endpoints | Phase 2 |
| `app/schemas/batch_dossier.py` | Pydantic schemas | Phase 2 |
| `alembic/versions/xxx_finding_v21_fields.py` | New Finding columns | Phase 1 |
| `alembic/versions/xxx_batch_dossiers.py` | Dossier tables | Phase 2 |
| `tests/synthetic/` | Synthetic test library | Phase 0-1 |
| `docs/validation/` | IQ/OQ/PQ templates | Phase 1-2 |

### Capabilities That Do NOT Exist

OCR/ICR/IWR, IDP Engine, page boundary preservation, scan quality assessment, knowledge graph, CPV/SPC trending, complex table extraction, LIMS/MES/ERP integration, multi-language support, large document chunking, structured explanation traces, 4-state verification, evidence package completeness, modular review packs, Layer 0 classification, CDMO multi-sponsor tenancy, synthetic test library, assessment provenance records.

---

**END OF ARCHITECTURE PROPOSAL v2.1**

*This document incorporates competitive intelligence from 10+ competitors and cross-sector stress testing across pharma, biologics, sterile, API, medical devices, dietary supplements, cell/gene therapy, blood/plasma, and CDMO scenarios. Technical claims verified against codebase as of May 27, 2026.*

*v2.0 → v2.1 changelog: Renamed module from "MBR" to "Batch & Lot Record Review." Added Sections 2 (Sector Routing), 9 (Modular Review Packs), 10 (Field Criticality), 17 (CDMO Architecture), 20 (Synthetic Test Library), 21 (Validation Strategy), 22 (Stress Test Gaps — 13 additional design considerations including multi-market compliance, cross-document conflict detection, content hash dedup, BPR versioning, post-disposition amendment, campaign manufacturing, partial assessment recovery, ERP/LIMS/MES integration schemas, controlled substance overlay, combination product dual-framework, Part 11 e-signatures, compounding pharmacy high-throughput mode, regulatory submission report generation). Updated all sections for: Gray verification state, disposition readiness reframing, evidence package completeness gate, provider-agnostic IDP, assessment provenance, structured explanation trace (dropped SHAP label), role-based dashboards, performance KPIs, post-disposition dossier reopening status. Restructured phases for sector-aware rollout.*
