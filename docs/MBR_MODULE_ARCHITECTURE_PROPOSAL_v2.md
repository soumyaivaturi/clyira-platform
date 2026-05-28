# Clyira MBR / Batch Record Review Module

## Architecture Proposal v2.0

**Date:** May 27, 2026
**Author:** Clyira Product Team
**Status:** DRAFT — Pending Product Owner Decision
**Classification:** Internal / Confidential
**Changelog:** v2.0 incorporates competitive intelligence from Aizon, Tulip, A&M/Deloitte, CPV-Auto, PwC, Assyro, Mareana, Acodis, BizData360, CDMO World — reshaping pipeline design, handwriting strategy, disposition model, and explainability layer.

---

## Table of Contents

1. Product Definition
2. Competitive Intelligence (NEW)
3. User Roles
4. Core User Workflow
5. Processing Pipeline (Updated — IDP Engine layer added)
6. IDP Engine Architecture (NEW)
7. Handwriting and Scan Strategy (Updated — Three-tier OCR→ICR→IWR)
8. Rule Engine Design
9. Finding Model (Updated — Dual confidence scoring)
10. Human Review Controls (Updated — Three-color verification, Shadow mode)
11. Disposition Model (Updated — 4-tier disposition)
12. Knowledge Graph Consideration (NEW)
13. Cross-Batch CPV/SPC Trending (NEW)
14. Explainability and Auditability (NEW)
15. Data Model Proposal (Updated)
16. UI Proposal (Updated)
17. Phased Implementation Options (Updated)
18. Risks and Open Questions (Updated)
19. Recommendation (Updated)
20. Appendix: Codebase Inventory

---

## 1. Product Definition

### 1.1 What This Module Is

The MBR / Batch Record Review module is an AI-assisted review support tool that helps QA reviewers process batch production records (BPRs) — whether paper-based, scanned, hybrid, or PDF — by organizing records into structured, evidence-linked review packages, surfacing potential issues, and requiring human verification before any disposition decision.

It extends Clyira's existing neuro-symbolic assessment pipeline (L1-L11) to a new document type: executed batch production records. It also introduces a new architectural concept — the Batch Dossier — that aggregates multiple related documents (BPR, deviations, CAPAs, QC results) into a lot-level view for batch release readiness.

### 1.2 What This Module Is NOT

This module does NOT:

- Replace MES (Manufacturing Execution System) or eBR (Electronic Batch Record) systems
- Approve or release a batch — final QA disposition remains a human-owned decision
- Replace human QA review — it supports and augments reviewers, not substitutes them
- Provide "fully automated QA" or "guaranteed compliance"
- Generate batch records — it reviews records that have already been executed
- Function as a real-time shop floor data capture system

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

The MBR module leverages ALL of this existing infrastructure. A batch record uploaded today would flow through the same pipeline as a CAPA or deviation — just with different checks defined in a different DTAP profile.

### 1.4 How It Differs from Competitors

| Dimension | MES/eBR (Apprentice, Tulip) | IDP/Extraction (Acodis) | AI Batch Review (Mareana, Aizon) | Clyira MBR Module |
|---|---|---|---|---|
| Primary function | Execute and capture batch records during manufacturing | Extract structured data from documents | AI-powered review and anomaly detection | Assess completed records for compliance gaps + lot-level readiness |
| When in lifecycle | During manufacturing | Post-manufacturing extraction | Post-manufacturing review | Post-manufacturing, supports release decision |
| Data source | Real-time shop floor data | Scanned/PDF batch records | MES data + documents | Any document format Clyira supports |
| Scope | Single batch record | Single batch record | Single batch or cross-batch trends | Batch dossier: BPR + deviations + CAPAs + QC results |
| Output | Completed eBR | Extracted data + exceptions | Anomaly alerts + dashboards | Scored findings + enforcement matches + disposition readiness |
| Cross-document | No (siloed to single eBR) | No | Limited (trending across batches) | Yes (lot-level cross-reference with dossier) |
| Regulatory intelligence | None (execution tool) | Limited (completeness checks) | Process monitoring, no enforcement matching | Full L1-L11 including L9 enforcement pattern matching |
| Explainability | N/A | Field-level confidence | Varies (Aizon has SHAP) | SHAP-style per finding + evidence linking |
| Disposition model | Binary pass/fail | N/A | Varies | 4-tier: Release / Conditional / Hold / Reject |
| Knowledge graph | No | No | Yes (Mareana — genealogy graph) | Considered for Phase 2+ (see Section 12) |
| Handwriting | N/A (digital capture) | ICR+IWR with HITL | Limited | Three-tier OCR→ICR→IWR with confidence gating |
| Price point | $500K-$2M+ for MES | ~€200K/year | Enterprise pricing | Within existing Clyira subscription |

### 1.5 Competitive Positioning

Clyira occupies a unique position in the market. Using Acodis's 4-category landscape model for document intelligence vendors, Clyira sits at the intersection of two categories:

- **ML Document Automation** — Foundation model-driven document understanding (IDP engine for extraction)
- **Rule-Based Compliance Enforcement** — DTAP-driven deterministic assessment with regulatory intelligence

No competitor bridges both categories. Acodis is strong on extraction but thin on compliance rules. Mareana has a knowledge graph but lacks the enforcement pattern matching and longitudinal analysis (L9-L10). MES vendors don't do post-hoc review at all. Consulting frameworks (PwC, A&M) describe what to build but don't ship product.

The Batch Dossier concept remains Clyira's most distinctive differentiator: a single lot-level view that connects the batch record to its deviations, CAPAs, and QC results, with cross-document correlation and a composite disposition readiness score. No competitor offers this.

### 1.6 Compliance Positioning (Critical)

All language in the module, UI, reports, and API responses MUST use safe language:

**Use:** AI-assisted review, potential issue, human verification required, reviewer confirmation needed, evidence-linked finding, final QA decision remains human-owned, supports reviewer decision, review support tool

**Never use:** AI approved, batch released, fully automated QA, no human review needed, guaranteed compliant, FDA-compliant by default

This is especially critical given FDA's April 2026 Purolea warning letter — the first enforcement action citing AI over-reliance. Clyira must position itself as a tool that enhances human review, never replaces it.

### 1.7 Data Privacy Commitment

Following CPV-Auto's explicit policy model: Clyira does NOT train on client data. Customer batch records, assessments, and corrections are never used to train foundation models. This must be a documented, auditable policy — not just a verbal assurance. Client data stays within the client's tenant boundary and is used only for that client's assessments and longitudinal analysis.

---

## 2. Competitive Intelligence (NEW in v2)

### 2.1 Competitor Landscape

Research across 10+ competitor products, consulting frameworks, and industry analyses identified design patterns that inform Clyira's architecture. The competitors fall into four categories:

**Category 1: MES / eBR Execution Platforms**
- Tulip, Apprentice.io, MasterControl — Real-time shop floor capture, not post-hoc review
- Key takeaway: Tulip's "Review by Exception" (RBE) pattern — QA reviews only the 1-2% of flagged exceptions, not every page. This maps directly to Clyira's finding severity system (Critical/High = must-review, Low/Info = exception-free pass).

**Category 2: IDP / Document Extraction**
- Acodis — Foundation model-based IDP with ICR, complex table extraction, and HITL verification
- Key takeaway: IDP must be a separate engine from assessment. Extraction confidence and assessment confidence are distinct concepts (see Section 6 and Section 9.3).

**Category 3: AI-Powered Batch Review / CPV**
- Mareana — GraphRAG over validated knowledge graph ("genealogy"), three-color verification (Green/Red/Blue)
- Aizon — Real-time process monitoring with SHAP/LIME explainability
- CPV-Auto — Automated CPV/SPC trending with explicit no-training-on-client-data policy
- Key takeaways: Knowledge graph constrains AI to synthesize from validated data only (architectural anti-hallucination). Cross-batch CPP/CQA trending is table-stakes for pharma QA.

**Category 4: Consulting Frameworks / Industry Analysis**
- PwC — AI GxP compliance framework: GAMP 5 validation, explainability as non-negotiable, HITL at every decision point
- A&M (Alvarez & Marsal) — Case study showing 40% cycle time reduction from AI-powered batch record mining at a pharma manufacturer
- Assyro — Regulatory guide identifying 4-tier disposition (Release/Conditional Release/Hold/Reject) and common batch record errors
- CDMO World — Human error analysis showing that most batch record issues stem from documentation errors, not manufacturing errors

### 2.2 Design Patterns Extracted from Competitors

The following 12 design patterns were identified across competitor analysis and are incorporated into v2:

| # | Pattern | Source | Clyira Integration |
|---|---|---|---|
| 1 | Review by Exception (RBE) | Tulip | Finding severity drives review scope — only Critical/High require active review |
| 2 | IDP as separate engine | Acodis | New IDP Engine layer between upload and assessment (Section 6) |
| 3 | Three-tier OCR→ICR→IWR | Acodis | Updated handwriting pipeline with character vs. word recognition (Section 7) |
| 4 | Dual confidence scoring | Acodis | Extraction confidence (how well OCR read) vs. Finding confidence (how confident AI assessment is) (Section 9.3) |
| 5 | Complex table extraction | Acodis | Dedicated table recognition component in IDP (Section 6) |
| 6 | GraphRAG over knowledge graph | Mareana | Knowledge graph consideration for Phase 2+ (Section 12) |
| 7 | Three-color verification | Mareana | Green (rule-verified pass) / Red (rule-verified fail) / Blue (AI-assisted) finding classification (Section 10) |
| 8 | Shadow/parallel review mode | Tulip | AI runs alongside human review to calibrate thresholds before go-live (Section 10.4) |
| 9 | 4-tier disposition | Assyro | Release / Conditional Release / Hold / Reject — replaces binary pass/fail (Section 11) |
| 10 | Cross-batch CPV/SPC trending | CPV-Auto, Mareana | Statistical trending of CPP/CQA across lots (Section 13) |
| 11 | SHAP-style explainability | PwC, Aizon | Every AI-generated finding must explain why (Section 14) |
| 12 | No-training-on-client-data | CPV-Auto | Documented policy, not just verbal (Section 1.7) |

### 2.3 What Competitors Do Well That Clyira Should Learn From

**Mareana's architectural anti-hallucination:** Their knowledge graph ("batch genealogy") constrains AI to only synthesize answers from validated, connected data. If a raw material lot isn't in the graph, the AI can't invent a connection. This is a stronger anti-hallucination approach than post-hoc validation — it prevents hallucination by constraining the input space. Clyira's current `AntiHallucinationGate` validates after generation; a knowledge graph would prevent at the source.

**Acodis's separation of extraction and understanding:** Acodis treats IDP (Intelligent Document Processing) as a foundation layer that goes far beyond OCR. Their model does layout analysis, table detection, field classification, and semantic grouping BEFORE any compliance logic runs. Clyira currently jumps from raw text extraction to assessment — the v2 pipeline adds an IDP layer between them.

**Aizon's process-aware monitoring:** Aizon doesn't just review documents — it monitors the manufacturing process itself and detects anomalies in real-time. Clyira won't replicate this (we're post-hoc review, not real-time monitoring), but the principle of process-awareness should inform our L5 (Data Intelligence) checks: when reviewing CPP values, Clyira should understand process context, not just compare numbers.

**A&M's quantified ROI:** Their case study shows a specific pharma company reduced batch record review cycle time by 40% using AI-powered document mining. This is the benchmark Clyira should target and measure against.

### 2.4 What Competitors Get Wrong (Clyira's Opportunity)

**No lot-level cross-document view.** Every competitor we studied operates at the single-document level. Even Mareana's knowledge graph connects data points but doesn't present a dossier-level disposition dashboard. Clyira's Batch Dossier with release gates is genuinely differentiated.

**Weak or absent enforcement intelligence.** No competitor maps findings to real FDA warning letters and 483 observations. Clyira's L9 enforcement pattern matching (116 citations of 21 CFR 211.192 in FY2024) gives findings regulatory weight that competitors can't match.

**Binary disposition.** Most tools offer pass/fail. Assyro's 4-tier model (Release/Conditional/Hold/Reject) is more realistic and Clyira should adopt it (see Section 11).

**No longitudinal analysis.** No competitor tracks finding patterns across batches for the same product over time. Clyira's L10 already does this — it's a natural extension to MBR.

---

## 3. User Roles

### 3.1 Existing Clyira Roles (Already in Codebase)

The `User` model in `app/models/user.py` already has a `roles` column (JSONB). Existing roles are managed at the company level. The MBR module introduces role-specific workflows within batch review:

| Role | MBR Module Permissions | Description |
|---|---|---|
| QA Reviewer | Upload batch records, create batch dossiers, review findings, confirm/dismiss findings, mark human-verified, generate review memo | Primary user. Reviews batch records and makes finding-level decisions. |
| QA Approver | All QA Reviewer permissions + approve/reject dossier disposition, sign off on review report | Senior QA who makes the final disposition recommendation. |
| Manufacturing Reviewer | View batch dossier (read-only), respond to manufacturing-related findings, provide context on deviations | Manufacturing SME consulted for production-related findings. |
| QC Reviewer | Upload QC results/COAs, link QC data to dossier, respond to QC-related findings | Lab personnel who provide analytical data and context. |
| Admin | Configure MBR review settings, manage templates, define CPP/IPC ranges | Company administrator who sets up the module. |

### 3.2 Implementation Note

No new database model is needed for roles. The existing `User.roles` JSONB field supports arbitrary role assignments. The MBR module's permissions are enforced at the router level via FastAPI dependency injection (`app/core/dependencies.py`), consistent with existing Clyira patterns.

---

## 4. Core User Workflow

### 4.1 End-to-End Workflow

The workflow from upload to final review report:

**Step 1: Create Batch Dossier**
QA Reviewer creates a new BatchDossier, entering lot number, product, and manufacturing date. This is the container that will hold all documents related to this lot.

**Step 2: Upload Batch Record Package**
QA Reviewer uploads the executed BPR (PDF scan, eBR export, or hybrid document). The document goes through Clyira's upload pipeline: text extraction → IDP Engine (NEW in v2) → section identification → auto-classification as "MBR" → DTAP-007 assignment.

**Step 3: Attach Supporting Documents**
QA Reviewer (or other roles) attach related documents to the dossier: deviation reports (already assessed via DTAP-004), CAPAs (DTAP-002), QC test results (future DTAP-008), environmental monitoring records, equipment logs. Each document is assessed individually through its own DTAP.

**Step 4: Run Assessment**
Triggering assessment on the BPR runs the full L1-L11 pipeline:
- L1-L2: Structural/document control checks (rule engine)
- L3: Content quality (hybrid — LLM for semantic analysis)
- L4: Data integrity / ALCOA+ (hybrid — critical for batch records)
- L5: Data intelligence (hybrid — CPP/IPC range checking)
- L6: Cross-reference traceability (LLM — dossier-enhanced)
- L7: Lifecycle/timeliness (rule engine)
- L8: Regulatory compliance (LLM with RAG)
- L9: Enforcement pattern matching
- L10: Longitudinal analysis
- L11: Inspectability checks

**Step 5: Dossier-Level Aggregation (Micro-batching)**
After individual documents are assessed, the BatchDispositionService computes:
- Composite lot disposition score (weighted aggregate of individual scores)
- Release gate status: open deviations, open CAPAs, QC pass/fail, data integrity holds
- Cross-document findings: mismatches between batch record and deviation dates, missing deviation references
- **Micro-batching (NEW in v2):** Disposition score recalculates every time a linked document's assessment completes, so the dossier dashboard is always current as supporting documents are added and assessed.

**Step 6: Human Review (Three-Color Verification — NEW in v2)**
QA Reviewer sees the dossier dashboard with findings classified using three-color verification:
- **Green findings:** Rule-engine verified pass. Deterministic check passed with no ambiguity. Reviewer can skip unless they disagree.
- **Red findings:** Rule-engine verified fail. Deterministic check failed — requires reviewer action (confirm, dismiss with rationale, or correct).
- **Blue findings:** AI-assisted assessment. LLM-generated finding with confidence score. Requires human judgment to confirm or reject.

For each finding, the reviewer can: confirm (agree), dismiss with rationale, correct an extracted value, mark as human-verified, assign to SME, or escalate to QA Approver. Critical and high-severity findings require documented rationale if dismissed.

**Step 7: Disposition Decision (4-Tier — NEW in v2)**
Once all findings are addressed, the QA Approver reviews the dossier and selects from four disposition levels:
- **Release:** All gates pass, no unresolved critical/high findings
- **Conditional Release:** Minor open items with documented justification
- **Hold:** Pending further investigation or additional data
- **Reject:** Fundamental quality or data integrity failures

This is a human decision — Clyira provides evidence and analysis but does not make the decision.

**Step 8: Export Review Report**
Generate an audit-ready review report: complete finding list, reviewer actions and rationale, disposition recommendation, three-color finding classification, all evidence-linked to source pages, Part 11-compliant signatures and timestamps.

---

## 5. Processing Pipeline (Updated in v2)

### 5.1 What Exists Today

The following pipeline is already built and operational in the Clyira codebase:

| Stage | Exists? | Implementation |
|---|---|---|
| Document upload + storage | YES | `DocumentService.upload_document()` → Supabase or local storage |
| PDF text extraction | YES | pdfplumber (primary), PyPDF2 (fallback) in `_extract_text_from_bytes()` |
| DOCX text extraction | YES | python-docx library |
| Table extraction from PDF | YES | pdfplumber `extract_tables()` with pipe-delimited output |
| Section identification | YES | Heuristic parser in `_identify_sections()` |
| Auto-classification | YES (needs MBR additions) | `_auto_classify()` — currently handles SOP, CAPA, ATM, Deviation, LIR, Validation |
| DTAP resolution | YES | `DTAPRegistry.resolve()` |
| Rule engine (deterministic checks) | YES | `RuleEngine.run()` with `_check_{level}_{name}` convention |
| LLM engine (semantic analysis) | YES | `LLMEngine.run()` with Groq/Gemini providers |
| Enforcement matching | YES | `EnforcementEngine.run()` with BM25 search across FDA observations |
| Anti-hallucination validation | YES | `AntiHallucinationGate.validate()` |
| Score calculation | YES | `ScoringEngine.calculate()` with severity deductions + caps |
| Remediation generation | YES | `LLMEngine.generate_remediation()` |
| Finding persistence | YES | `AssessmentService._store_findings()` → Finding model |
| Audit trail | YES | `Audit` model with user, entity, action, timestamp |
| Part 11 tamper-evident hashing | YES | `compute_hash()` on assessment completion |

### 5.2 What Needs to Be Added

| Stage | Status | What's Needed |
|---|---|---|
| MBR auto-classification | GAP | Add patterns to `_auto_classify()` for batch record keywords |
| DTAP-007 (MBR profile) | BUILT (needs design review) | 87 checks across L1-L11 — built in prior session, needs review |
| MBR rule engine checks | BUILT (needs design review) | 44 deterministic checks — built in prior session, needs review |
| **IDP Engine (NEW in v2)** | NOT BUILT | Separate engine between upload and assessment — layout analysis, table detection, field extraction with per-field confidence (see Section 6) |
| OCR for scanned documents | NOT BUILT | See Section 7 (updated three-tier strategy) |
| Page-level evidence linking | NOT BUILT | Current extraction loses page boundaries |
| Batch Dossier model | NOT BUILT | New entity linking lot → documents |
| Batch Disposition Service | NOT BUILT | Cross-document aggregation + gate logic + micro-batching |
| DTAP-008 (QC Test Record) | NOT BUILT | New profile for lab test results / COA |
| Dossier API routes | NOT BUILT | CRUD + disposition endpoints |
| Dossier UI | NOT BUILT | Lot-level dashboard, gate status, composite score, three-color verification |
| Review memo generation | NOT BUILT | AI-generated draft QA review summary |
| Page/scan quality detection | NOT BUILT | Scan quality scoring, missing page detection |
| **Three-color finding classification** | NOT BUILT | Green/Red/Blue tagging on each finding (see Section 10) |
| **4-tier disposition model** | NOT BUILT | Release/Conditional/Hold/Reject logic (see Section 11) |
| **Cross-batch CPV/SPC trending** | NOT BUILT | Statistical trending of CPP/CQA across lots (see Section 13) |
| **SHAP-style explainability** | NOT BUILT | Per-finding explanation of reasoning (see Section 14) |

### 5.3 Future Pipeline (Full Vision — Updated in v2)

This is the eventual target pipeline for MBR processing. Items marked [FUTURE] are not in the initial build:

1. **Intake** — Upload executed BPR + supporting documents to BatchDossier
2. **Preprocessing** — [FUTURE] Page-level segmentation, scan quality scoring, blank page detection, duplicate page detection
3. **IDP Engine (NEW)** — Intelligent Document Processing: layout analysis, table detection, field classification, semantic grouping, per-field confidence scoring. Decoupled from assessment. See Section 6.
4. **OCR/ICR/IWR Extraction** — [FUTURE] Three-tier recognition pipeline: OCR (printed) → ICR (handwritten characters) → IWR (handwritten words). See Section 7.
5. **Section Classification** — Existing `_identify_sections()` enhanced with IDP-informed section boundaries
6. **MBR Template Mapping** — [FUTURE] Compare executed record against approved MBR template to detect deviations from master
7. **Deterministic Rule Engine** — Existing `RuleEngine` with DTAP-007 checks → produces Green/Red findings
8. **AI Co-QA Reasoning** — Existing `LLMEngine` for semantic analysis (L3, L6, L8) → produces Blue findings
9. **Enforcement Matching** — Existing `EnforcementEngine` for L9
10. **Dossier Aggregation** — `BatchDispositionService` for cross-document analysis with micro-batching
11. **Anti-Hallucination Validation** — Existing `AntiHallucinationGate` + [FUTURE] knowledge graph constraint
12. **Explainability Layer (NEW)** — SHAP-style reasoning trace per finding (see Section 14)
13. **Human Verification** — Three-color review workflow with required rationale for Red/Blue findings
14. **Disposition** — 4-tier disposition decision (Release/Conditional/Hold/Reject)
15. **Report Generation** — Audit-ready review report export
16. **Feedback/Learning Layer** — [FUTURE] Store reviewer corrections to improve future assessments
17. **CPV/SPC Trending** — [FUTURE] Cross-batch statistical process trending (see Section 13)

---

## 6. IDP Engine Architecture (NEW in v2)

### 6.1 Why a Separate IDP Layer

Competitive analysis — particularly Acodis's architecture — revealed a critical gap in Clyira's current pipeline. Today, Clyira goes directly from raw text extraction (pdfplumber) to assessment (rule engine + LLM). This works for well-structured documents (SOPs, CAPAs) but is insufficient for batch records, which contain:

- Complex multi-column tables (IPC results, material dispensing logs, yield calculations)
- Mixed content types on a single page (pre-printed form fields + handwritten values + stamps)
- Hierarchical section structures that pdfplumber's flat text extraction flattens
- Field-value pairs where the relationship between label and value depends on spatial layout

IDP (Intelligent Document Processing) is a separate concern from assessment. Extraction answers "what does this document contain?" Assessment answers "does this document comply?" Mixing them produces both worse extraction and worse assessment.

### 6.2 IDP Engine Design

The IDP Engine sits between upload/text extraction and assessment in the pipeline:

```
Upload → Raw Text Extraction (existing) → IDP Engine (NEW) → Assessment Pipeline (existing)
```

The IDP Engine's output is a structured document representation stored in `Document.extracted_sections` (JSONB), enriched from the current flat section list to a richer structure:

```
IDPOutput:
├── pages[]:
│   ├── page_number: Integer
│   ├── page_type: String [form, narrative, table, signature, blank]
│   ├── regions[]:
│   │   ├── type: String [text, table, handwriting, signature, stamp, checkbox]
│   │   ├── bounding_box: [x0, y0, x1, y1]
│   │   ├── content: String (extracted text or structured data)
│   │   ├── confidence: Float (extraction confidence 0-1)
│   │   └── recognition_method: String [digital, ocr, icr, iwr, manual]
│   └── tables[]:
│       ├── headers: String[]
│       ├── rows: String[][]
│       ├── confidence: Float
│       └── table_type: String [ipc_results, material_list, yield_calc, equipment_log, other]
├── fields[]:
│   ├── field_name: String (e.g., "Batch Number", "Manufacturing Date")
│   ├── field_value: String
│   ├── source_page: Integer
│   ├── confidence: Float (extraction confidence)
│   ├── recognition_method: String
│   └── requires_human_verification: Boolean (True if confidence < threshold or CPP/IPC field)
├── sections[]:
│   ├── title: String
│   ├── start_page: Integer
│   ├── end_page: Integer
│   ├── content_summary: String
│   └── subsections[]: (recursive)
└── metadata:
    ├── total_pages: Integer
    ├── document_type_detected: String
    ├── scan_quality_score: Float (nullable)
    ├── handwriting_detected: Boolean
    ├── table_count: Integer
    └── blank_page_indices: Integer[]
```

### 6.3 Complex Table Extraction (from Acodis)

Batch records are full of tables: IPC results, material dispensing logs, yield calculations, environmental monitoring data, equipment cleaning records. Acodis identifies complex table extraction as a dedicated capability because:

- Tables often span multiple pages
- Merged cells, nested headers, and irregular row heights are common
- Table context (what the table represents) matters as much as the data
- Values in tables are often the critical parameters the assessment needs

Clyira's IDP Engine must include a table recognition component that:
- Detects table boundaries on each page
- Classifies table type (IPC, material list, yield, etc.)
- Extracts headers and rows into structured arrays
- Assigns per-cell confidence scores
- Handles multi-page table continuation
- Flags low-confidence cells for human verification

### 6.4 Phased IDP Implementation

**Phase 1 (MVP):** Use existing pdfplumber table extraction enhanced with page-boundary preservation. Store page numbers alongside extracted text. Classify sections using existing heuristics plus MBR-specific patterns. No OCR.

**Phase 2:** Add layout analysis using a document layout model (e.g., LayoutLM, DocTR, or similar). Detect tables, form fields, text blocks, and handwriting zones. Produce the structured IDPOutput above for digital PDFs.

**Phase 3:** Integrate OCR/ICR/IWR for scanned documents (see Section 7). The IDP Engine becomes the orchestrator that routes each detected region to the appropriate recognition engine.

---

## 7. Handwriting and Scan Strategy (Updated in v2)

### 7.1 Current State: What Clyira Can and Cannot Do

**Can do today:** Extract text from digitally-generated PDFs (eBR exports, typed forms) using pdfplumber. This handles the majority of modern batch records.

**Cannot do today:** OCR on scanned paper documents, handwriting recognition, scan quality assessment, page boundary detection, image-based field extraction.

### 7.2 Honest Assessment

Handwriting recognition in pharmaceutical batch records is an unsolved problem at production quality. The industry's own data shows:

- Batch records contain a mix of pre-printed text, typed entries, handwritten values, handwritten initials, checkmarks, strikethroughs, and stamps
- Handwriting quality varies dramatically between operators
- Critical values (weights, temperatures, times) are often handwritten
- FDA requires that records be "legible" (21 CFR 211.188) but many are not

No vendor — including Acodis — claims perfect handwriting recognition. Acodis reports ">95% accuracy depending on input quality" with human-in-the-loop verification.

### 7.3 Three-Tier Recognition Pipeline (NEW in v2 — from Acodis)

Acodis's architecture distinguishes three levels of recognition, each with different capability and confidence characteristics:

**Tier 1: OCR (Optical Character Recognition)**
- Target: Printed/typed text in scanned documents
- Technology: Tesseract, Google Vision, or similar
- Expected accuracy: 98-99% for clean scans
- Use case: Pre-printed form fields, typed entries, document headers/footers, printed lot numbers

**Tier 2: ICR (Intelligent Character Recognition)**
- Target: Individual handwritten characters (digits, individual letters)
- Technology: Specialized ML models trained on handwritten character datasets
- Expected accuracy: 90-95% depending on handwriting quality
- Use case: Handwritten numeric values (weights, temperatures, pH readings), dates, individual initials
- Key distinction from OCR: ICR models are trained specifically on handwritten characters and understand pen-stroke patterns, not just pixel patterns

**Tier 3: IWR (Intelligent Word Recognition)**
- Target: Handwritten words and phrases in context
- Technology: Sequence models (RNN/Transformer-based) that understand word-level context
- Expected accuracy: 80-90% for common pharmaceutical terminology, lower for free-text
- Use case: Handwritten notes, deviation descriptions, operator comments, narrative entries
- Key distinction from ICR: IWR uses language context and pharmaceutical vocabulary to resolve ambiguous characters (e.g., "5" vs "S" is resolved by knowing the field expects a number)

### 7.4 Risk-Controlled Phasing (Updated in v2)

**Phase 1 — No OCR.** Accept digital PDFs and eBR exports only. This covers the growing segment of companies using electronic systems. For companies with paper records, they can manually type critical values into Clyira's review workflow.

**Phase 2 — OCR for printed text (Tier 1).** Add Tesseract or similar OCR for scanned documents that contain primarily printed/typed text. Confidence scoring on every extracted value. Any value below 90% confidence is flagged for human verification.

**Phase 3 — Handwriting zone detection + ICR (Tier 2).** Detect regions of the document that contain handwriting. For numeric fields and simple character sequences (dates, initials, checkmarks), apply ICR with character-level confidence scoring. Fields below confidence threshold → human verification required. Narrative handwriting → flagged as "handwriting detected — human verification required" without attempting full recognition.

**Phase 4 — IWR for contextual recognition (Tier 3).** Add word-level recognition for handwritten entries in known field contexts. Use pharmaceutical vocabulary constraints to improve accuracy. Always with dual confidence (extraction + assessment) and mandatory human verification for CPPs/IPCs.

### 7.5 Key Principles (Updated in v2)

- Never present an OCR/ICR/IWR-extracted value as ground truth. Always show confidence and source image.
- **Dual confidence (NEW):** Track extraction confidence (how well the recognition engine read the value) separately from finding confidence (how confident the assessment engine is about the compliance check). A finding can have high assessment confidence even when extraction confidence is low — because the finding IS that extraction confidence is low.
- Critical parameters (CPPs, IPCs, yields, expiry dates) extracted via any recognition tier MUST be human-verified before use in any calculation or compliance check.
- Store every reviewer correction. This creates a labeled dataset for future model improvement.
- Link every extracted value to its source page and bounding box coordinates.
- If recognition confidence is below threshold for a required field, the finding should state "value could not be reliably extracted — human verification required" rather than guessing.
- **No-training-on-client-data boundary:** Reviewer corrections improve extraction within the client's tenant only. They are never pooled across clients or used for foundation model training.

---

## 8. Rule Engine Design

### 8.1 Existing Rule Engine Architecture

Clyira's rule engine (`app/engines/rule_engine.py`, ~7100 lines) uses a naming convention: `_check_{level_lower}_{check_name}(self, context)`. Each method returns a `FindingResult` or `None`. Checks that are listed in a DTAP profile but don't have a matching rule engine method automatically fall back to batched LLM calls.

### 8.2 MBR-Specific Rule Categories

These map to DTAP-007 levels:

**L1 — Structural Completeness (Rule Engine) → Green/Red findings**
- Required sections present (Bill of Materials, Equipment List, Processing Steps, IPCs, Yield Calculations, Packaging, Signatures)
- Product identification complete (name, code, strength, dosage form)
- Batch number format validation
- Batch size and theoretical yield specified
- Manufacturing and expiry/retest dates present
- Page numbering sequential (if detectable)

**L2 — Document Control (Rule Engine) → Green/Red findings**
- Executed record matches master BPR version
- Operator identification on each critical step
- QA reviewer signature present
- Dual verification signatures where required
- Supervisory approval documented

**L3 — Content Quality (Hybrid — LLM + Rules) → Blue findings**
- Processing steps sufficiently detailed
- In-process control descriptions adequate
- Yield calculation methodology clear
- Deviation narrative completeness (if deviations occurred)
- Environmental monitoring data referenced
- Equipment cleaning status documented

**L4 — Data Integrity / ALCOA+ (Hybrid — Highest Weight) → Red for rule violations, Blue for AI-detected**
- Corrections use single-line strikethrough with initials and date
- No blank required fields (white-out, blank spaces where values expected)
- Timestamps in logical sequence (no backdating)
- Duplicate data detection (identical entries across different steps)
- No pre-signed blank pages
- Contemporaneous recording indicators
- Attributable entries (who did what, when)

**L5 — Data Intelligence (Hybrid) → Blue findings**
- CPP values within specified ranges
- IPC results within acceptance criteria
- Yield within expected range (typically 90-110% of theoretical)
- Material balance calculations correct
- Environmental monitoring within limits

**L6 — Cross-Reference Traceability (LLM, Dossier-Enhanced) → Blue findings**
- Deviation references in BPR match actual deviation documents in dossier
- CAPA references traceable to real CAPAs
- Equipment IDs match equipment logs
- Raw material lot numbers traceable to COAs
- Cleaning validation references current

**L7 — Lifecycle / Timeliness (Rule Engine) → Green/Red findings**
- Batch review completed within defined timeframe (typically 30 days)
- All deviations closed before release
- No open action items at time of release
- Reprocessing properly documented if applicable
- Yield check performed at appropriate stage

**L8 — Regulatory Compliance (LLM with RAG) → Blue findings**
- 21 CFR 211.186 (MBR requirements) compliance
- 21 CFR 211.188 (BPR requirements) compliance
- 21 CFR 211.192 (production record review) compliance
- 21 CFR Part 11 (electronic records) if applicable
- EU GMP Chapter 4 / Annex 11 if applicable
- ICH Q7 (API) or Q10 (PQS) alignment

**L9 — Enforcement Pattern Matching (Existing Engine) → Red findings (enforcement-matched)**
- Match findings against FDA 483 observations and warning letters
- 21 CFR 211.192 was cited 116 times in FY2024 — second most common 483 observation
- Severity elevation for patterns matching consent decree triggers

**L10 — Longitudinal Analysis (Existing Engine) → Blue findings**
- Compare batch record quality across lots for same product
- Detect recurring findings across batches
- Department and operator trending

**L11 — Inspectability (Rule Engine) → Green/Red findings**
- No TBD placeholders or draft language
- All pages accounted for
- Internal cross-section consistency (batch number matches throughout)
- Effective date present
- Version control complete

### 8.3 Three-Color Finding Classification (NEW in v2)

Each finding produced by the rule engine or LLM engine is tagged with a verification color:

| Color | Source | Meaning | Reviewer Action |
|---|---|---|---|
| Green | Rule engine deterministic pass | System-verified pass. The check ran, the criterion was met. | Minimal — review only if reviewer disagrees with the rule's logic |
| Red | Rule engine deterministic fail | System-verified fail. The check ran, the criterion was NOT met. | Must address: confirm finding, dismiss with rationale, or correct data |
| Blue | LLM engine semantic assessment | AI-assisted finding. Confidence score attached. Requires human judgment. | Must review: confirm, reject, or request more context |

This classification is stored as a `verification_color` field on the Finding model (see Section 9).

### 8.4 What Was Already Built (Needs Design Review)

In the prior session, 44 deterministic rule engine checks were implemented and 87 total checks were defined in DTAP-007. These were built before this architecture discussion and should be reviewed against this proposal before being considered final. The code exists in:
- `app/dtap/profiles/mbr.py` — DTAP-007 profile definition
- `app/engines/rule_engine.py` — Rule engine check implementations (end of file)
- `app/dtap/registry.py` — MBR registered in DTAPRegistry

---

## 9. Finding Model (Updated in v2)

### 9.1 Existing Finding Model (Already Built)

Clyira already has a comprehensive `Finding` model in `app/models/assessment.py`. Each finding includes:

| Field | Type | Description |
|---|---|---|
| level | String | L1 through L11 |
| severity | String | critical, high, medium, low, info |
| category | String | e.g., "missing_section", "data_integrity", "unsigned_approval" |
| title | String | Human-readable finding title |
| description | Text | Detailed description of the issue |
| evidence | Text | What triggered the finding (extracted from document) |
| location | String | Section reference in document |
| regulatory_citation | Text | Specific regulation (e.g., "21 CFR 211.188(b)(3)") |
| citation_type | String | direct, traceability, substantive |
| agency | String | FDA, EMA, MHRA, etc. |
| enforcement_match | Boolean | Matched to real enforcement precedent |
| enforcement_context | Text | Details of enforcement match |
| severity_elevated | Boolean | Severity increased due to enforcement pattern |
| suggestion_draft | Text | AI-generated remediation suggestion |
| next_step_text | Text | Recommended next action |
| remediation_priority | Integer | 1=immediate, 2=short-term, 3=medium-term |
| status | String | open, acknowledged, in_progress, resolved, disputed |
| response_text | Text | Reviewer's response/rationale |
| confidence_score | Float | Model confidence (LLM findings) |
| validated | Boolean | Passed anti-hallucination gate |

### 9.2 What ChatGPT Proposed vs. What Exists

ChatGPT's proposal suggested creating a new `MBRFinding` model with fields like severity, category, description, source_page, section, expected, observed, confidence, human_verification_required, recommended_reviewer_action, status, reviewer_rationale.

**This is unnecessary.** The existing `Finding` model already covers all of these fields, and in most cases with more depth (enforcement matching, citation types, remediation priority). Creating a separate MBR-specific finding model would break Clyira's architecture — all document types produce the same `Finding` entity, enabling cross-document comparison, longitudinal analysis, and consistent scoring.

### 9.3 Additions Needed for MBR Context (Updated in v2)

The following fields should be added to the existing `Finding` model (or stored in a JSONB metadata column):

- **source_page** (Integer, nullable) — Page number where the finding was detected. Currently, findings have `location` (section name) but not page number. This is valuable for batch records where reviewers flip to specific pages.

- **human_verification_required** (Boolean, default False) — Flag for findings where the underlying data came from OCR/ICR/IWR extraction with low confidence, or where the check involves a critical parameter that regulatory guidance requires human verification.

- **verification_color** (String, nullable — "green", "red", "blue") — NEW in v2. Three-color classification from Mareana's pattern. Green = rule-verified pass, Red = rule-verified fail, Blue = AI-assisted finding. Drives the reviewer's workflow: Green findings need minimal attention, Red and Blue require active review.

- **extraction_confidence** (Float, nullable) — NEW in v2. Distinct from `confidence_score` (which is the AI assessment's confidence in the finding itself). Extraction confidence is how well the IDP/OCR engine read the underlying value. A finding can have high `confidence_score` (the AI is confident this is an issue) but low `extraction_confidence` (the value that triggered it was poorly extracted). This dual-confidence concept comes from Acodis's architecture.

- **explanation_trace** (Text, nullable) — NEW in v2. SHAP-style explanation of why this finding was generated. For rule engine findings: which rule, what input, what threshold. For LLM findings: key evidence passages, reasoning chain, contributing factors. See Section 14.

These can be added as nullable columns in a future migration without breaking existing functionality.

---

## 10. Human Review Controls (Updated in v2)

### 10.1 Existing Review Workflow

Clyira already has a finding status workflow in the `Finding` model:
- **open** → Finding detected, awaiting review
- **acknowledged** → Reviewer has seen and agrees
- **in_progress** → Remediation underway
- **resolved** → Fixed, with evidence/rationale
- **disputed** → Reviewer disagrees, with documented reason

The scoring engine respects these states: resolved findings have 0x deduction weight, in_progress has 0.5x, open/disputed have full 1.0x weight.

### 10.2 MBR-Specific Review Controls

For batch record review, stricter controls are needed:

**Dismiss-all prevention:** A "dismiss all" button must not exist. Each finding must be individually addressed with rationale.

**Critical finding escalation:** Critical and high severity findings cannot be dismissed without documented rationale of at least 50 characters. Dismissals of critical findings should trigger notification to QA Approver.

**Human verification queue:** Findings flagged with `human_verification_required = True` (from OCR confidence or critical parameter checks) must be explicitly verified by a human before the dossier can move to disposition.

**SME assignment:** A finding can be assigned to a specific user (Manufacturing Reviewer, QC Reviewer) for domain-specific response. The `actioned_by` field on Finding already supports tracking who took action.

**Escalation to QA Approver:** Any reviewer can escalate a finding to the QA Approver if they cannot make a determination. This adds the finding to the Approver's review queue.

**Correction workflow:** When a reviewer corrects an extracted value (e.g., OCR misread "5.2" as "52"), the correction is stored as a `FeedbackCorrection` record linking the original value, corrected value, finding ID, and source coordinates. This serves as training data for future extraction improvement within the client's tenant.

### 10.3 Three-Color Review Workflow (NEW in v2)

Building on Mareana's Green/Red/Blue verification system, the review workflow is structured by finding color:

**Green finding review:** The finding card shows a green badge and the rule that passed. The reviewer sees a compact summary. If they agree, no action needed — green findings auto-progress to "acknowledged" status after the reviewer views the dossier. If the reviewer disagrees with a green pass, they can override to create a manual finding.

**Red finding review:** The finding card shows a red badge with the specific rule that failed, the expected value/condition, and the observed value/condition. The reviewer MUST take action: confirm (the issue is real), dismiss with rationale (the rule doesn't apply in this context), or correct the underlying data (the extraction was wrong).

**Blue finding review:** The finding card shows a blue badge with the AI's confidence score and explanation trace. The reviewer sees the evidence passages the AI used and the reasoning chain. The reviewer MUST confirm or reject the finding. If rejected, the reviewer provides a reason that becomes training feedback.

### 10.4 Shadow / Parallel Review Mode (NEW in v2 — from Tulip)

Before deploying the MBR module in production, a calibration phase is needed. Tulip's "shadow mode" pattern:

**How it works:** The AI assessment runs in parallel with the human reviewer's normal process. The reviewer completes their review as they normally would (without Clyira), and separately Clyira runs its assessment on the same batch record. Afterwards, the results are compared:
- Findings the AI caught that the human missed → validates AI value
- Findings the human caught that the AI missed → identifies gaps in rules/LLM prompts
- Findings both caught → confirms alignment
- False positives from AI → identifies rules that need tuning

**Why it matters:** Shadow mode builds trust, calibrates confidence thresholds, and provides quantitative evidence of the module's value — all before the module is used for actual disposition decisions. It also satisfies the GAMP 5 validation requirement for performance qualification (PQ).

**Implementation:** Shadow mode is a configuration flag on the BatchDossier (or company settings). When enabled:
- Assessment runs normally and produces findings
- Disposition gates are calculated but not enforced
- The UI shows a "Shadow Mode" banner making it clear this is calibration, not production
- A comparison report can be generated showing AI vs. human alignment metrics

### 10.5 Implementation Approach

Most of this is handled through the existing `Finding.status` and `Finding.response_text` fields plus UI logic. The new data needed:

- `verification_color` on Finding (new column — see Section 9.3)
- `FeedbackCorrection` model (new table) — for storing value corrections
- Business logic in the router layer to enforce dismissal rules (minimum rationale length, escalation triggers)
- UI changes to the finding card component to support color-coded review, assignment, and verification workflows
- Shadow mode configuration flag and comparison report generation

---

## 11. Disposition Model (NEW in v2 — from Assyro)

### 11.1 Why 4-Tier Disposition

The v1 proposal had a simple disposition concept: release, reject, or hold. Assyro's regulatory analysis identifies a richer model that better reflects pharmaceutical reality:

- **Release:** All quality criteria met, all gates pass, batch is fit for distribution
- **Conditional Release:** Minor open items exist but a documented risk assessment justifies release (e.g., a low-severity finding about documentation format that doesn't affect product quality)
- **Hold:** Significant open items require further investigation before a disposition decision can be made (e.g., pending stability data, lab retesting, or deviation investigation)
- **Reject:** Fundamental quality failure — batch cannot be released (e.g., out-of-spec results, data integrity fraud indicators, critical manufacturing deviations)

### 11.2 Disposition Scoring Logic

The `BatchDispositionService` computes a disposition recommendation based on:

**Automatic gates (binary — any failure blocks Release):**
- Data integrity hold on any document in the dossier → cannot Release
- Open critical findings → cannot Release
- Open deviations without closure → cannot Release
- Open CAPAs linked to this batch → cannot Release (can Conditional Release with rationale)

**Score-based recommendation:**
- Composite dossier score ≥ 90 (Excellent) → Recommend Release
- Composite dossier score 80-89 (Good) → Recommend Release or Conditional Release depending on open findings
- Composite dossier score 65-79 (Moderate) → Recommend Conditional Release or Hold
- Composite dossier score 50-64 (Poor) → Recommend Hold
- Composite dossier score < 50 (Critical) → Recommend Reject

**The recommendation is advisory only.** The QA Approver makes the final decision and must document their rationale, especially if they choose a disposition that differs from the system recommendation.

### 11.3 Conditional Release Requirements

When a QA Approver selects "Conditional Release," the system requires:
- Documented risk assessment (minimum 100 characters)
- List of specific conditions that must be fulfilled
- Timeline for condition fulfillment
- Responsible person for each condition
- Follow-up review date

This creates an auditable record that satisfies regulatory expectations for conditional release decisions.

---

## 12. Knowledge Graph Consideration (NEW in v2 — from Mareana)

### 12.1 What Mareana Does

Mareana builds a "batch genealogy" knowledge graph that connects:
- Raw materials → suppliers → COAs → specifications
- Equipment → cleaning records → calibration status
- Operators → training records → certifications
- Process parameters → IPC results → yield
- Deviations → CAPAs → effectiveness checks
- Batches → products → stability data

Their AI (GraphRAG) can only synthesize answers from data that exists as validated nodes and edges in this graph. If a connection doesn't exist in the graph, the AI cannot invent it. This is architectural anti-hallucination — stronger than post-hoc validation because it constrains the input space, not just the output.

### 12.2 How This Maps to Clyira

Clyira's Batch Dossier already creates the seed of a knowledge graph: it links a lot number to a BPR, deviations, CAPAs, and QC results. The dossier IS a mini-graph centered on a batch.

A full knowledge graph would extend this to:
- Connect raw material lots in the BPR to COAs uploaded as supporting documents
- Link equipment IDs mentioned in the BPR to equipment qualification documents
- Map operator names to training records
- Connect deviations mentioned in the BPR to the actual deviation documents in the system

### 12.3 Design Decision: Phase 2+

Building a full pharmaceutical knowledge graph is a significant infrastructure investment (graph database, entity resolution, relationship extraction, ongoing maintenance). For the MBR MVP, Clyira should:

**Phase 1 (MVP):** Use the Batch Dossier's document-linking as a lightweight graph. L6 cross-reference checks operate on the documents linked to the dossier. This is sufficient for initial value.

**Phase 2:** Add entity extraction from documents — extract raw material lots, equipment IDs, operator names as structured entities stored alongside the document. Enable cross-document entity matching within a dossier (e.g., "lot number X is mentioned in the BPR and has a COA in the dossier").

**Phase 3:** Build a proper knowledge graph (likely using a graph layer on top of PostgreSQL, e.g., Apache AGE, or a separate graph database like Neo4j). Enable GraphRAG for L6 and L8 checks — the LLM can only reference data that exists as validated nodes in the graph.

### 12.4 Key Principle

Even without a formal knowledge graph, Clyira should adopt Mareana's core principle: **constrain AI to validated data.** The LLM engine's RAG context for batch record assessment should include only the documents linked to the dossier, the regulatory corpus, and the enforcement database. It should never be allowed to "imagine" connections or data that doesn't exist in the system.

---

## 13. Cross-Batch CPV/SPC Trending (NEW in v2 — from CPV-Auto, Mareana)

### 13.1 What CPV/SPC Trending Is

Continued Process Verification (CPV) requires manufacturers to monitor Critical Process Parameters (CPPs) and Critical Quality Attributes (CQAs) across batches over time to confirm the process remains in a state of control. This is mandated by ICH Q8/Q10 and FDA Process Validation Guidance (Stage 3).

Statistical Process Control (SPC) charts — control charts, capability indices (Cpk), trend analysis — are the standard tools. CPV-Auto and Mareana both offer automated CPV trending as core features.

### 13.2 How This Fits Clyira's Architecture

Clyira's L10 (Longitudinal Analysis) already compares findings across assessments for the same document type. Extending this to batch-level CPV trending is a natural evolution:

**Data source:** When Clyira assesses a BPR and extracts CPP/IPC values (via IDP Engine or manual entry), those values are stored as structured data in the assessment record.

**Trending logic:** Across multiple batches of the same product, Clyira can:
- Plot CPP/CQA values on control charts (X-bar, R-chart, individual/moving range)
- Calculate Cpk/Ppk capability indices
- Detect trends (7+ points trending in one direction), shifts (8+ points on one side of center line), and outliers (beyond 3σ)
- Flag process drift before it results in OOS results

**Output:** A CPV trending dashboard accessible from the Batch Dossier or product-level view, showing the historical trajectory of key parameters.

### 13.3 Design Decision: Phase 2+

CPV trending requires a critical mass of batch data to be meaningful (typically 15-30 batches minimum for statistical validity). For the MBR MVP:

**Phase 1 (MVP):** Extract and store CPP/IPC values from assessed BPRs. No trending yet — the data is being accumulated.

**Phase 2:** Once sufficient batches are assessed for a product, enable trending views. Basic SPC charts (individual/moving range), trend detection rules (Western Electric rules), and integration with L10 longitudinal findings.

**Phase 3:** Full CPV reporting — automated CPV reports per product, Cpk/Ppk calculations, process capability trending, export to regulatory submission format (FDA Annual Product Review).

---

## 14. Explainability and Auditability (NEW in v2 — from PwC, Aizon)

### 14.1 Why Explainability Is Non-Negotiable

PwC's AI GxP framework states that for any AI system used in regulated pharmaceutical contexts, explainability is not a feature — it's a requirement. Regulators (FDA, EMA) expect that any AI-assisted decision can be traced back to specific inputs, reasoning, and evidence. The April 2026 Purolea warning letter reinforced this: FDA expects companies to explain HOW AI reached its conclusions, not just what the conclusions are.

Aizon implements SHAP (SHapley Additive exPlanations) and LIME (Local Interpretable Model-agnostic Explanations) for their process monitoring models. While Clyira uses a different architecture (LLM-based rather than traditional ML), the principle is the same: every finding must be explainable.

### 14.2 Explainability Design for Clyira

Each finding's `explanation_trace` field (new in v2) contains a structured reasoning trace:

**For rule engine findings (Green/Red):**
```
{
  "type": "deterministic",
  "rule_id": "l4_correction_format",
  "input_values": {"correction_text": "5.2 crossed out, 5.3 written beside it", "has_initials": false, "has_date": false},
  "threshold": "ALCOA+ requires corrections with single-line strikethrough, initials, and date",
  "result": "FAIL — initials and date not detected alongside correction",
  "regulatory_basis": "21 CFR 211.188(b), ALCOA+ principles"
}
```

**For LLM findings (Blue):**
```
{
  "type": "ai_assisted",
  "model": "gemini-2.5-flash",
  "confidence": 0.87,
  "evidence_passages": [
    {"page": 12, "text": "Mixing time: 45 minutes", "relevance": "CPP value extracted"},
    {"page": 3, "text": "Mixing time specification: 30-40 minutes", "relevance": "Specification limit"}
  ],
  "reasoning": "Extracted mixing time (45 min) exceeds the upper specification limit (40 min) stated on page 3. This represents a CPP excursion that should be investigated.",
  "anti_hallucination_check": "PASSED — both values traced to specific document locations",
  "contributing_factors": ["value_out_of_range", "cpp_parameter", "no_deviation_reference"]
}
```

### 14.3 GAMP 5 Validation Alignment

PwC's framework maps AI validation to GAMP 5 lifecycle stages:

| GAMP 5 Stage | Clyira Equivalent |
|---|---|
| Validation Master Plan (VMP) | Architecture proposal (this document) + validation protocol |
| Model Development | DTAP profile design, rule engine implementation, LLM prompt engineering |
| Design Qualification (DQ) | Architecture review, design spec sign-off |
| Installation Qualification (IQ) | Deployment verification, dependency check |
| Operational Qualification (OQ) | Rule engine unit tests, LLM output validation against known batch records |
| Performance Qualification (PQ) | Shadow/parallel review mode (Section 10.4), statistical comparison with human reviewers |
| Continuous Monitoring | L10 longitudinal analysis, finding accuracy tracking, feedback correction rates |

Clyira should provide validation support documentation (IQ/OQ/PQ templates) that customers can use within their own quality systems. This is a differentiator — most AI vendors leave validation entirely to the customer.

---

## 15. Data Model Proposal (Updated in v2)

### 15.1 New Entities Required

**NOTE: These are proposed interfaces only. No implementation yet.**

#### BatchDossier (New Model — Updated in v2)

```
BatchDossier
├── id: UUID (primary key)
├── company_id: FK → companies
├── created_by: FK → users
├── lot_number: String (unique per company)
├── product_name: String
├── product_code: String (nullable)
├── dosage_form: String (nullable)
├── batch_size: String (nullable)
├── manufacturing_site: String (nullable)
├── manufacturing_date: String (nullable)
├── target_release_date: String (nullable)
├── status: String [draft, under_review, pending_disposition, released, conditionally_released, on_hold, rejected]
├── disposition_score: Float (nullable) — composite of individual doc scores
├── disposition_band: String (nullable) — Excellent/Good/Moderate/Poor/Critical
├── disposition_recommendation: String (nullable) — Release/Conditional/Hold/Reject (AI-generated)
├── disposition_decision: String (nullable) — Release/Conditional/Hold/Reject (human-made) [NEW in v2]
├── disposition_rationale: Text (nullable) — QA Approver's documented rationale [NEW in v2]
├── conditional_release_conditions: JSONB (nullable) — if Conditional Release, list of conditions [NEW in v2]
├── gate_open_deviations: Boolean (default True) — blocks if open deviations exist
├── gate_open_capas: Boolean (default True) — blocks if open CAPAs exist
├── gate_qc_complete: Boolean (default False) — all QC results linked and passing
├── gate_data_integrity: Boolean (default True) — blocks if any DI hold on any document
├── gate_all_findings_addressed: Boolean (default False) — all critical/high findings resolved
├── shadow_mode: Boolean (default False) — if True, dossier is in calibration mode [NEW in v2]
├── released_by: FK → users (nullable)
├── released_at: DateTime (nullable)
├── release_rationale: Text (nullable)
├── created_at: DateTime
├── updated_at: DateTime
```

#### BatchDossierDocument (Join Table)

```
BatchDossierDocument
├── id: UUID (primary key)
├── dossier_id: FK → batch_dossiers
├── document_id: FK → documents
├── role: String [primary_bpr, deviation, capa, qc_result, coa, environmental_monitoring, equipment_log, reprocessing_record, other]
├── sequence_order: Integer (nullable) — for ordering within role
├── notes: Text (nullable) — reviewer notes about this document's relevance
├── added_by: FK → users
├── added_at: DateTime
```

#### FeedbackCorrection (New Model)

```
FeedbackCorrection
├── id: UUID (primary key)
├── finding_id: FK → findings
├── document_id: FK → documents
├── corrected_by: FK → users
├── field_name: String — what field was corrected
├── original_value: String — what was extracted
├── corrected_value: String — what the human entered
├── source_page: Integer (nullable)
├── bounding_box: JSONB (nullable) — [x0, y0, x1, y1] of source region [NEW in v2]
├── extraction_confidence: Float (nullable) — original extraction confidence [NEW in v2]
├── recognition_method: String (nullable) — ocr/icr/iwr/digital [NEW in v2]
├── correction_rationale: Text (nullable)
├── created_at: DateTime
```

### 15.2 Existing Entities That Stay Unchanged

The following models are NOT modified — the MBR module uses them as-is:

- **Document** — BPR and supporting documents are regular Document records
- **Assessment** — Each document assessment uses the existing Assessment model
- **Finding** — All findings (MBR and otherwise) use the existing Finding model (with new nullable columns from Section 9.3)
- **Company** — Multi-tenant root, unchanged
- **User** — Role-based access, unchanged
- **Audit** — Audit trail, unchanged
- **DocumentReference** — Supporting documents can also use this existing mechanism
- **EnforcementRecord** — Enforcement matching is the same pipeline
- **RegulatoryCorpus** — Regulatory knowledge base, unchanged

### 15.3 Entities NOT Needed (Correcting ChatGPT's Proposal)

ChatGPT proposed these entities which are NOT required because they duplicate existing Clyira functionality:

- **MBRReviewJob** — This is the existing `Assessment` model
- **UploadedBatchFile** — This is the existing `Document` model
- **BatchRecordSection** — Already captured in `Document.extracted_sections` (JSONB)
- **ExtractedField** — Not needed in Phase 1. IDP Engine output goes into `Document.extracted_sections` JSONB. A separate `ExtractedField` table may be justified in Phase 2 when field-level confidence tracking and correction workflows become more granular.
- **MBRFinding** — This is the existing `Finding` model
- **ReviewerAction** — Already captured in `Finding.status`, `Finding.response_text`, `Finding.actioned_by`, and the `Audit` log
- **HumanVerificationItem** — A filtered view of findings where `human_verification_required = True`
- **ReviewReport** — A generated export (PDF/DOCX), not a stored entity
- **ProcessingAuditLog** — This is the existing `Audit` model

### 15.4 Document.extracted_sections Enhancement (NEW in v2)

The `Document.extracted_sections` JSONB column currently stores a flat list of section titles and content. For MBR documents processed through the IDP Engine, this column should store the richer `IDPOutput` structure defined in Section 6.2. The schema is backward-compatible — existing documents with flat section lists continue to work, while MBR documents get the enriched structure.

---

## 16. UI Proposal (Updated in v2)

### 16.1 Existing UI Architecture

Clyira's frontend is built with Next.js 14+ (App Router), React, TailwindCSS, TypeScript. The dashboard uses a `(dashboard)/` route group with pages for documents, assessments, readiness, inspections, evidence, audit, and settings.

### 16.2 New Screens Required

#### Batch Dossiers List — `/(dashboard)/batch-dossiers/page.tsx`
Table showing all batch dossiers for the company. Columns: lot number, product, status, disposition score/band, gate status (icons), disposition decision, manufacturing date, created by. Filters by status, product, date range, disposition decision. Shadow mode dossiers are visually distinct (dashed border or "Calibration" badge).

#### New Batch Dossier — `/(dashboard)/batch-dossiers/new/page.tsx`
Form to create a dossier: lot number, product name, product code, manufacturing date, manufacturing site. Upload primary BPR and optionally attach supporting documents. Toggle for shadow mode.

#### Dossier Dashboard — `/(dashboard)/batch-dossiers/[id]/page.tsx`
The core screen. Layout:

**Header:** Lot number, product, status badge, composite disposition score with band, disposition recommendation vs. decision (if different, highlighted)

**Gate Status Panel:** Visual checklist of release gates (green/red/amber icons)
- All deviations closed
- All CAPAs effective
- QC results complete and passing
- No data integrity holds
- All critical/high findings addressed

**Finding Summary by Color (NEW in v2):** Three-color breakdown
- Green findings: X pass / Y total (auto-acknowledged)
- Red findings: X addressed / Y total (require action)
- Blue findings: X confirmed / Y total (require review)

**Documents Panel:** Cards for each linked document showing: title, type/role, individual Clyira score, finding count by severity and color, assessment status

**Findings Summary:** Aggregated findings across all documents in the dossier, grouped by color first, then severity, filterable by document and level

**Timeline:** Chronological view of all actions taken on the dossier

**Disposition Panel (NEW in v2):** For QA Approver — 4-tier selection (Release/Conditional/Hold/Reject) with mandatory rationale, conditional release conditions form, and comparison against system recommendation.

#### Document Viewer (Enhanced) — `/(dashboard)/batch-dossiers/[id]/documents/[docId]/page.tsx`
Extends the existing document detail page with:
- Side-by-side view: original document (PDF render) on left, findings on right
- Click a finding to highlight the relevant section/page in the document
- Color-coded finding cards (green/red/blue badges)
- Extraction confidence indicators on IDP-extracted values
- Human verification queue for OCR/ICR/IWR-extracted values (future)
- Explanation trace expandable on each Blue finding

#### Shadow Mode Comparison (NEW in v2) — `/(dashboard)/batch-dossiers/[id]/shadow-report/page.tsx`
Available when dossier is in shadow mode. Shows:
- AI findings vs. human reviewer findings (side-by-side or Venn diagram)
- Alignment metrics: precision, recall, F1 for AI findings against human baseline
- False positive and false negative analysis
- Recommendations for threshold tuning

#### Review Report Export — Modal or dedicated page
Generate and download the audit-ready review report. Includes: dossier summary, all findings with three-color classification and reviewer actions/rationale, disposition recommendation and decision, explanation traces for Blue findings, all evidence-linked to source pages, Part 11-compliant signatures and timestamps.

### 16.3 Modifications to Existing Screens

- **Documents List:** Add "Batch Dossier" column showing which dossier (if any) a document belongs to
- **Dashboard:** Add "Batch Dossiers" card showing recent dossiers and their status
- **Navigation:** Add "Batch Review" item to sidebar navigation
- **Product View (NEW in v2):** Product-level page showing CPV/SPC trending charts across batches (Phase 2+)

---

## 17. Phased Implementation Options (Updated in v2)

### Phase 0: Architecture Only (This Document)

**What:** This document. No code changes.
**Complexity:** None.
**Best use case:** Team alignment, stakeholder/investor/advisor review before committing engineering resources.

### Phase 1: DTAP-007 Validation + Auto-Classify Fix (Quick Win)

**What:** Review already-built DTAP-007 profile and 44 rule engine checks against this v2 architecture proposal. Fix the `_auto_classify()` gap so MBR documents are recognized. Verify end-to-end with test documents. Add `verification_color` tagging (Green/Red for rule engine findings).
**Does not include:** Batch Dossier, IDP Engine, OCR, QC DTAP, new UI screens.
**Complexity:** Low (1-2 weeks).
**Value:** Proves the DTAP works, catches early design issues, gives customers a working single-document MBR assessment.

### Phase 2: Batch Dossier MVP

**What:** BatchDossier model + migration, BatchDispositionService with 4-tier disposition, dossier API routes, dossier UI (list + dashboard + document linking), micro-batching for score recalculation, three-color finding classification, shadow mode infrastructure, FeedbackCorrection model.
**Does not include:** IDP Engine, OCR/handwriting, MBR template mapping, CPV trending, knowledge graph.
**Complexity:** Medium (4-6 weeks).
**Value:** The differentiated product — lot-level cross-document batch review with 4-tier disposition. No competitor offers this.

### Phase 3: IDP Engine + Enhanced Extraction

**What:** IDP Engine layer (Section 6) for digital PDFs — page-boundary preservation, layout analysis, complex table extraction, per-field confidence scoring, structured IDPOutput in `Document.extracted_sections`. Dual confidence scoring (extraction + finding). Explanation traces (Section 14) for all findings.
**Does not include:** OCR/ICR/IWR, knowledge graph, CPV trending.
**Complexity:** Medium-High (4-6 weeks).
**Value:** Dramatically improves extraction quality for batch records, enables field-level evidence linking, provides explainability that satisfies GAMP 5 requirements.

### Phase 4: OCR/ICR/IWR + Handwriting

**What:** Three-tier recognition pipeline (Section 7). OCR for printed text in scanned documents. ICR for handwritten numeric values. IWR for contextual handwritten words. Human verification queue in UI. Scan quality scoring.
**Does not include:** Knowledge graph, CPV trending.
**Complexity:** High (6-8 weeks).
**Value:** Opens the market to paper-based batch record customers. Combined with IDP Engine, provides full extraction pipeline.

### Phase 5: CPV/SPC Trending + Knowledge Graph Foundations

**What:** Cross-batch CPV/SPC trending (Section 13). Extract and store CPP/IPC values from assessed BPRs. Basic SPC charts and trend detection. Entity extraction from documents for knowledge graph foundations. Product-level trending view.
**Does not include:** Full knowledge graph with GraphRAG.
**Complexity:** Medium (4-6 weeks).
**Value:** Addresses ICH Q8/Q10 CPV requirements. Provides the data accumulation foundation for future knowledge graph.

### Phase 6: Knowledge Graph + GraphRAG

**What:** Full knowledge graph (Section 12). Entity resolution across documents. Graph-constrained RAG for L6 and L8 checks. Architectural anti-hallucination.
**Complexity:** High (8-12 weeks).
**Value:** The strongest possible anti-hallucination architecture. Unique in the market.

### Alternative: QC Test Record First

**What:** DTAP-008 for QC test records, COA assessment checks, integration with existing assessment pipeline. Can be built in parallel with any phase above.
**Complexity:** Low-Medium (2-3 weeks).
**Value:** QC test records are simpler (more structured, fewer template variations) and may be a better starting point. Also makes the dossier's QC gate functional.

---

## 18. Risks and Open Questions (Updated in v2)

### 18.1 Technical Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Handwriting accuracy** | High | Three-tier pipeline with confidence gating. Never rely on OCR/ICR/IWR for critical decisions. Always require human verification. Phase in cautiously. See Section 7. |
| **Scan quality** | Medium | Accept digital PDFs first. Add scan quality scoring in Phase 3. Reject illegible scans with clear messaging. |
| **Template variability** | High | Every company (and every CMO) uses different batch record templates. Clyira's DTAP approach is template-agnostic (assesses content, not layout), but section identification will struggle with unfamiliar formats. IDP Engine (Section 6) + LLM fallback helps here. |
| **Page boundary loss** | Medium | Current pdfplumber extraction concatenates pages. IDP Engine (Phase 3) preserves page boundaries. In Phase 1, add page markers to existing extraction. |
| **Validation burden** | High | Any AI tool used in GMP context should be validated per GAMP 5 / FDA guidance. Shadow mode (Section 10.4) supports PQ. Clyira should provide validation documentation templates. See Section 14.3. |
| **False negatives** | Medium | More dangerous than false positives — a missed critical finding could lead to releasing a deficient batch. Mitigation: conservative thresholds, human verification requirements, clear disclaimer that Clyira supplements but does not replace human review. Shadow mode quantifies false negative rate. |
| **LLM cost scaling** | Low | Batch records can be very long (100+ pages). Consider chunking strategy for long documents. IDP Engine pre-processing reduces what the LLM needs to analyze. |
| **Explainability completeness** | Medium (NEW) | LLM explanation traces depend on the model's ability to articulate reasoning. Not all findings will have equally clear explanations. Mitigation: rule engine findings (Green/Red) have deterministic, fully traceable explanations. Blue findings include evidence passages and confidence, acknowledging uncertainty. |
| **Knowledge graph complexity** | High (NEW) | A full knowledge graph is a significant infrastructure investment. Mitigation: defer to Phase 5-6, build incrementally on dossier document linking. |

### 18.2 Product Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Reviewer overreliance on AI** | High | This is the Purolea risk. Mitigation: never auto-approve, three-color verification makes AI findings (Blue) visually distinct from rule-based findings (Green/Red), require human verification for critical findings, include prominent disclaimers, design UI to encourage engagement. |
| **Confusion with batch release** | High | Customers may expect Clyira to "release" batches. Clear product positioning: Clyira supports review, humans make decisions. 4-tier disposition with mandatory rationale reinforces human ownership. |
| **Scope creep toward MES** | Medium | The Batch Dossier concept could expand toward full manufacturing execution. Maintain clear boundary: Clyira is post-hoc review, not execution. |
| **Integration complexity** | Medium | Customers will want Clyira to pull data from their MES, LIMS, ERP. Initial version requires manual upload. API integrations are Phase 2+. |
| **Market timing** | Low | FDA's increasing focus on AI in pharma (Purolea letter, AI Guiding Principles) creates both opportunity (demand for responsible AI tools) and risk (regulatory scrutiny). Clyira's explainability and human-in-the-loop design directly address FDA concerns. |
| **Green-finding rubber-stamping** | Medium (NEW) | Risk that reviewers auto-skip all Green findings without reading them. Mitigation: periodic random audit requiring Green finding review, aggregate Green finding stats in review report, shadow mode comparison to verify Green findings are truly reliable. |

### 18.3 Open Questions for Product Owner

1. **Target customer profile:** Companies with digital eBR exports? Paper-based? Both? This determines whether IDP/OCR is Phase 1 or Phase 3-4.

2. **Dossier vs. single document priority:** Should the dossier concept be built first (more differentiated) or should single-document MBR assessment ship first (faster, lower risk)?

3. **QC Test Record timing:** Build alongside MBR or separately? The dossier value proposition is stronger with both.

4. **CMO scenario priority:** Virtual pharma companies receiving batch records from multiple CMOs is a strong use case. Does the module need CMO-specific features (template mapping, multi-format handling) in the initial release?

5. **Review memo generation:** How important is generating a draft QA review memo vs. just presenting findings? This is additional LLM work but could be high-value.

6. **Pricing model:** Is this included in the existing Clyira subscription or an add-on module? This affects build priority and scope.

7. **Validation support:** Should Clyira provide validation documentation (IQ/OQ/PQ templates, test scripts)? This is a significant differentiator but adds documentation work. (PwC's framework suggests this is expected.)

8. **Shadow mode duration (NEW):** How many batches should be reviewed in shadow mode before the module is considered calibrated? Industry standard for PQ is typically 3 consecutive batches, but AI calibration may need more.

9. **Conditional release workflow (NEW):** Does the conditional release feature require integration with the customer's change control or CAPA system to track condition fulfillment? Or is manual tracking sufficient for MVP?

10. **CPV trending scope (NEW):** Should Clyira's CPV trending be limited to within-product trending, or should it support cross-product comparisons (e.g., all products manufactured on the same line)?

---

## 19. Recommendation (Updated in v2)

Based on the analysis of the existing codebase, competitive landscape research (10+ competitor products), regulatory environment, and stress testing against real scenarios:

**Recommended path: Phase 1 → Phase 2 → Phase 3, with QC Test Record (DTAP-008) built in parallel starting in Phase 2.**

The reasoning:

**Phase 1 (1-2 weeks)** validates the DTAP-007 pipeline works end-to-end with test documents. Low risk, quick feedback loop, catches design issues early. Adds three-color finding classification.

**Phase 2 (4-6 weeks)** delivers the Batch Dossier MVP — Clyira's most differentiated feature. No competitor offers lot-level cross-document batch review with 4-tier disposition, release gates, and micro-batching. This is shippable and valuable for companies with digital/eBR records.

**Phase 3 (4-6 weeks)** adds the IDP Engine for better extraction quality and the explainability layer for GAMP 5 compliance. This makes the product defensible against regulatory scrutiny.

**QC Test Record (2-3 weeks, parallel)** completes the dossier's QC gate, making the "360-degree batch disposition" vision fully functional.

**Phases 4-6** (OCR/handwriting, CPV trending, knowledge graph) are Phase 2+ investments that expand the addressable market and deepen competitive moats, but are not required for initial product value.

**Total to first shippable product (Phase 1 + Phase 2): 5-8 weeks.**

**Why this sequence works:**
- Competitive research confirms the Batch Dossier is genuinely differentiated — build it first
- Three-color verification and 4-tier disposition are design patterns validated across multiple competitors — incorporate from the start
- Shadow mode de-risks deployment by providing quantitative calibration data
- IDP Engine and explainability (Phase 3) address the PwC/GAMP 5 validation requirements that enterprise customers will demand
- OCR/handwriting (Phase 4) opens the paper-based market — important but not urgent given eBR adoption trends
- Knowledge graph (Phase 6) is the long-term competitive moat but requires data accumulation from earlier phases

**However, final decision should be made by the product owner** based on customer feedback, market timing, and resource availability.

---

## 20. Appendix: Codebase Inventory

### Files That Exist and Are Relevant

| File | Status | Notes |
|---|---|---|
| `app/dtap/profiles/mbr.py` | Built (needs review) | DTAP-007 with 87 checks — built before this architecture discussion |
| `app/dtap/registry.py` | Modified | MBR_DTAP imported and registered |
| `app/engines/rule_engine.py` | Modified | 44 MBR rule checks added at end of file |
| `app/services/document_service.py` | Needs modification | `_auto_classify()` missing MBR patterns |
| `app/engines/orchestrator.py` | No changes needed | Existing pipeline handles MBR via DTAP |
| `app/engines/scoring.py` | No changes needed | Existing scoring works with DTAP-007 weights |
| `app/engines/enforcement_engine.py` | No changes needed | 211.192 already in enforcement corpus |
| `app/engines/validator.py` | No changes needed | Anti-hallucination gate is DTAP-agnostic |
| `app/models/assessment.py` | Minor additions needed | source_page, human_verification_required, verification_color, extraction_confidence, explanation_trace |
| `app/models/document.py` | Minor enhancement | extracted_sections JSONB to support IDPOutput structure |

### Files That Need to Be Created

| File | Purpose | Phase |
|---|---|---|
| `app/models/batch_dossier.py` | BatchDossier and BatchDossierDocument models | Phase 2 |
| `app/models/feedback_correction.py` | FeedbackCorrection model | Phase 2 |
| `app/services/batch_disposition_service.py` | Dossier aggregation, gate logic, 4-tier disposition, micro-batching | Phase 2 |
| `app/services/idp_engine.py` | IDP Engine — layout analysis, table detection, field extraction | Phase 3 |
| `app/routers/batch_dossiers.py` | API endpoints for dossier CRUD and disposition | Phase 2 |
| `app/schemas/batch_dossier.py` | Pydantic request/response schemas | Phase 2 |
| `alembic/versions/xxx_add_batch_dossiers.py` | Database migration for dossier tables | Phase 2 |
| `alembic/versions/xxx_add_finding_v2_fields.py` | Migration for new Finding columns | Phase 1 |
| `apps/web/src/app/(dashboard)/batch-dossiers/` | Frontend pages (list, new, detail, shadow report) | Phase 2 |
| `app/services/cpv_trending_service.py` | Cross-batch CPV/SPC trending logic | Phase 5 |

### Capabilities That Do NOT Exist in the Codebase

For accuracy, the following capabilities referenced in this proposal do NOT currently exist in Clyira and should not be assumed:

- OCR / Tesseract / handwriting recognition — NOT built
- ICR / IWR recognition engines — NOT built
- IDP Engine (layout analysis, complex table extraction) — NOT built
- Image-based field extraction — NOT built
- Page boundary preservation in text extraction — NOT built
- Scan quality assessment — NOT built
- Missing/duplicate page detection — NOT built
- MBR template comparison (master vs. executed) — NOT built
- CPP/IPC range validation against specifications — NOT built (checks exist in DTAP but are LLM-fallback, not rule-based with actual spec values)
- LIMS / MES / ERP integration — NOT built
- COA generation — NOT built
- Handwriting zone detection — NOT built
- Knowledge graph / graph database — NOT built
- Cross-batch CPV/SPC trending — NOT built
- SHAP-style explainability traces — NOT built
- Three-color finding classification — NOT built (needs new column on Finding)
- 4-tier disposition model — NOT built (needs BatchDossier model)
- Shadow/parallel review mode — NOT built

---

**END OF ARCHITECTURE PROPOSAL v2.0**

*This document incorporates competitive intelligence from Aizon, Tulip, A&M, CPV-Auto, PwC, Assyro, Mareana, Acodis, BizData360, and CDMO World. All technical claims about the codebase have been verified against the actual source code as of May 27, 2026.*

*v1.0 → v2.0 changelog: Added Sections 2, 6, 11, 12, 13, 14. Updated Sections 1.4, 4, 5, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20. Key additions: IDP Engine architecture, three-tier OCR→ICR→IWR pipeline, three-color verification, 4-tier disposition, knowledge graph consideration, CPV/SPC trending, SHAP-style explainability, shadow review mode, dual confidence scoring, complex table extraction, data privacy commitment.*
