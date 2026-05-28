# Clyira MBR / Batch Record Review Module

## Architecture Proposal v1.0

**Date:** May 27, 2026
**Author:** Clyira Product Team
**Status:** DRAFT — Pending Product Owner Decision
**Classification:** Internal / Confidential

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

### 1.4 How It Differs from MES/eBR/Batch Release Tools

| Dimension | MES/eBR (Apprentice, Tulip, MasterControl) | Acodis (Batch Record Review) | Clyira MBR Module |
|---|---|---|---|
| Primary function | Execute and capture batch records during manufacturing | Extract and review completed batch records | Assess completed records for compliance gaps + lot-level readiness |
| When in lifecycle | During manufacturing | After manufacturing, before release | After manufacturing, supports release decision |
| Data source | Real-time shop floor data | Scanned/PDF batch records | Any document format Clyira supports |
| Scope | Single batch record | Single batch record | Batch dossier: BPR + deviations + CAPAs + QC results |
| Output | Completed eBR | Extracted data + exceptions | Scored findings + enforcement matches + disposition readiness |
| Cross-document | No (siloed to single eBR) | No | Yes (lot-level cross-reference) |
| Regulatory intelligence | None (execution tool) | Limited (completeness checks) | Full L1-L11 including enforcement pattern matching |
| Price point | $500K-$2M+ for MES | ~€200K/year | Within existing Clyira subscription |

### 1.5 Competitive Positioning

Clyira occupies a unique position: it is neither an execution tool (MES) nor a pure extraction tool (Acodis). Its differentiation is regulatory intelligence depth — the same L9 enforcement matching, L10 longitudinal analysis, and DTAP-driven assessment that makes Clyira's CAPA and deviation reviews valuable applies equally to batch records.

The Batch Dossier concept is something no competitor currently offers: a single lot-level view that connects the batch record to its deviations, CAPAs, and QC results, with cross-document correlation and a composite disposition readiness score.

### 1.6 Compliance Positioning (Critical)

All language in the module, UI, reports, and API responses MUST use safe language:

**Use:** AI-assisted review, potential issue, human verification required, reviewer confirmation needed, evidence-linked finding, final QA decision remains human-owned, supports reviewer decision, review support tool

**Never use:** AI approved, batch released, fully automated QA, no human review needed, guaranteed compliant, FDA-compliant by default

This is especially critical given FDA's April 2026 Purolea warning letter — the first enforcement action citing AI over-reliance. Clyira must position itself as a tool that enhances human review, never replaces it.

---

## 2. User Roles

### 2.1 Existing Clyira Roles (Already in Codebase)

The `User` model in `app/models/user.py` already has a `roles` column (JSONB). Existing roles are managed at the company level. The MBR module introduces role-specific workflows within batch review:

| Role | MBR Module Permissions | Description |
|---|---|---|
| QA Reviewer | Upload batch records, create batch dossiers, review findings, confirm/dismiss findings, mark human-verified, generate review memo | Primary user. Reviews batch records and makes finding-level decisions. |
| QA Approver | All QA Reviewer permissions + approve/reject dossier disposition, sign off on review report | Senior QA who makes the final disposition recommendation (release/reject/hold). |
| Manufacturing Reviewer | View batch dossier (read-only), respond to manufacturing-related findings, provide context on deviations | Manufacturing SME consulted for production-related findings. |
| QC Reviewer | Upload QC results/COAs, link QC data to dossier, respond to QC-related findings | Lab personnel who provide analytical data and context. |
| Admin | Configure MBR review settings, manage templates, define CPP/IPC ranges | Company administrator who sets up the module. |

### 2.2 Implementation Note

No new database model is needed for roles. The existing `User.roles` JSONB field supports arbitrary role assignments. The MBR module's permissions are enforced at the router level via FastAPI dependency injection (`app/core/dependencies.py`), consistent with existing Clyira patterns.

---

## 3. Core User Workflow

### 3.1 End-to-End Workflow

The workflow from upload to final review report:

**Step 1: Create Batch Dossier**
QA Reviewer creates a new BatchDossier, entering lot number, product, and manufacturing date. This is the container that will hold all documents related to this lot.

**Step 2: Upload Batch Record Package**
QA Reviewer uploads the executed BPR (PDF scan, eBR export, or hybrid document). The document goes through Clyira's existing upload pipeline: text extraction, section identification, auto-classification as "MBR", DTAP-007 assignment.

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

**Step 5: Dossier-Level Aggregation**
After individual documents are assessed, the BatchDispositionService computes:
- Composite lot disposition score (weighted aggregate of individual scores)
- Release gate status: open deviations, open CAPAs, QC pass/fail, data integrity holds
- Cross-document findings: mismatches between batch record and deviation dates, missing deviation references, etc.

**Step 6: Human Review**
QA Reviewer sees the dossier dashboard with findings grouped by severity and document. For each finding, they can: confirm (agree with finding), dismiss with rationale (explain why it's not applicable), correct an extracted value, mark as human-verified, assign to SME for review, escalate to QA Approver. Critical and high-severity findings require documented rationale if dismissed.

**Step 7: Disposition Decision**
Once all findings are addressed (confirmed, dismissed, or resolved), the QA Approver reviews the dossier and makes a recommendation: Release, Reject, or Hold for further investigation. This is a human decision — Clyira provides evidence and analysis but does not make the decision.

**Step 8: Export Review Report**
Generate an audit-ready review report: complete finding list, reviewer actions and rationale, disposition recommendation, all evidence-linked to source pages, Part 11-compliant signatures and timestamps.

---

## 4. Processing Pipeline

### 4.1 What Exists Today

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

### 4.2 What Needs to Be Added

| Stage | Status | What's Needed |
|---|---|---|
| MBR auto-classification | GAP | Add patterns to `_auto_classify()` for batch record keywords |
| DTAP-007 (MBR profile) | BUILT (needs design review) | 87 checks across L1-L11 — built in prior session, needs review |
| MBR rule engine checks | BUILT (needs design review) | 44 deterministic checks — built in prior session, needs review |
| OCR for scanned documents | NOT BUILT | See Section 5 (Handwriting Strategy) |
| Page-level evidence linking | NOT BUILT | Current extraction loses page boundaries |
| Batch Dossier model | NOT BUILT | New entity linking lot → documents |
| Batch Disposition Service | NOT BUILT | Cross-document aggregation + gate logic |
| DTAP-008 (QC Test Record) | NOT BUILT | New profile for lab test results / COA |
| Dossier API routes | NOT BUILT | CRUD + disposition endpoints |
| Dossier UI | NOT BUILT | Lot-level dashboard, gate status, composite score |
| Review memo generation | NOT BUILT | AI-generated draft QA review summary |
| Page/scan quality detection | NOT BUILT | Scan quality scoring, missing page detection |

### 4.3 Future Pipeline (Full Vision)

This is the eventual target pipeline for MBR processing. Items marked [FUTURE] are not in the initial build:

1. **Intake** — Upload executed BPR + supporting documents to BatchDossier
2. **Preprocessing** — [FUTURE] Page-level segmentation, scan quality scoring, blank page detection, duplicate page detection
3. **OCR/Extraction** — [FUTURE] For scanned documents: OCR with confidence scoring, handwriting zone detection (see Section 5)
4. **Section Classification** — Existing `_identify_sections()` enhanced with MBR-specific section headers
5. **MBR Template Mapping** — [FUTURE] Compare executed record against approved MBR template to detect deviations from master
6. **Deterministic Rule Engine** — Existing `RuleEngine` with DTAP-007 checks
7. **AI Co-QA Reasoning** — Existing `LLMEngine` for semantic analysis (L3, L6, L8)
8. **Enforcement Matching** — Existing `EnforcementEngine` for L9
9. **Dossier Aggregation** — NEW `BatchDispositionService` for cross-document analysis
10. **Anti-Hallucination Validation** — Existing `AntiHallucinationGate`
11. **Human Verification** — Finding review workflow with required rationale
12. **Report Generation** — Audit-ready review report export
13. **Feedback/Learning Layer** — [FUTURE] Store reviewer corrections to improve future assessments

---

## 5. Handwriting and Scan Strategy

### 5.1 Current State: What Clyira Can and Cannot Do

**Can do today:** Extract text from digitally-generated PDFs (eBR exports, typed forms) using pdfplumber. This handles the majority of modern batch records.

**Cannot do today:** OCR on scanned paper documents, handwriting recognition, scan quality assessment, page boundary detection, image-based field extraction.

### 5.2 Honest Assessment

Handwriting recognition in pharmaceutical batch records is an unsolved problem at production quality. The industry's own data shows:

- Batch records contain a mix of pre-printed text, typed entries, handwritten values, handwritten initials, checkmarks, strikethroughs, and stamps
- Handwriting quality varies dramatically between operators
- Critical values (weights, temperatures, times) are often handwritten
- FDA requires that records be "legible" (21 CFR 211.188) but many are not

No vendor — including Acodis — claims perfect handwriting recognition. Acodis reports ">95% accuracy depending on input quality" with human-in-the-loop verification.

### 5.3 Risk-Controlled Strategy (Do Not Assume Perfect Recognition)

Phase 1 — No OCR. Accept digital PDFs and eBR exports only. This covers the growing segment of companies using electronic systems. For companies with paper records, they can manually type critical values into Clyira's review workflow.

Phase 2 — Basic OCR for printed text. Add Tesseract or similar OCR for scanned documents that contain primarily printed/typed text. Confidence scoring on every extracted value. Any value below 90% confidence is flagged for human verification.

Phase 3 — Handwriting zone detection (not recognition). Detect regions of the document that contain handwriting. Flag them as "handwriting detected — human verification required" without attempting to read the handwriting. The reviewer sees the source image and manually enters the value.

Phase 4 — Selective handwriting extraction. For simple, high-confidence fields only (dates, initials, checkmarks, numeric values). Never for narrative text. Always with confidence scoring and mandatory human verification for critical parameters (CPPs, IPCs, yields).

### 5.4 Key Principles

- Never present an OCR-extracted value as ground truth. Always show confidence and source image.
- Critical parameters (CPPs, IPCs, yields, expiry dates) extracted via OCR MUST be human-verified before use in any calculation or compliance check.
- Store every reviewer correction. This creates a labeled dataset for future model improvement.
- Link every extracted value to its source page and bounding box coordinates.
- If OCR confidence is below threshold for a required field, the finding should state "value could not be reliably extracted — human verification required" rather than guessing.

---

## 6. Rule Engine Design

### 6.1 Existing Rule Engine Architecture

Clyira's rule engine (`app/engines/rule_engine.py`, ~7100 lines) uses a naming convention: `_check_{level_lower}_{check_name}(self, context)`. Each method returns a `FindingResult` or `None`. Checks that are listed in a DTAP profile but don't have a matching rule engine method automatically fall back to batched LLM calls.

### 6.2 MBR-Specific Rule Categories

These map to DTAP-007 levels:

**L1 — Structural Completeness (Rule Engine)**
- Required sections present (Bill of Materials, Equipment List, Processing Steps, IPCs, Yield Calculations, Packaging, Signatures)
- Product identification complete (name, code, strength, dosage form)
- Batch number format validation
- Batch size and theoretical yield specified
- Manufacturing and expiry/retest dates present
- Page numbering sequential (if detectable)

**L2 — Document Control (Rule Engine)**
- Executed record matches master BPR version
- Operator identification on each critical step
- QA reviewer signature present
- Dual verification signatures where required
- Supervisory approval documented

**L3 — Content Quality (Hybrid — LLM + Rules)**
- Processing steps sufficiently detailed
- In-process control descriptions adequate
- Yield calculation methodology clear
- Deviation narrative completeness (if deviations occurred)
- Environmental monitoring data referenced
- Equipment cleaning status documented

**L4 — Data Integrity / ALCOA+ (Hybrid — Highest Weight)**
- Corrections use single-line strikethrough with initials and date
- No blank required fields (white-out, blank spaces where values expected)
- Timestamps in logical sequence (no backdating)
- Duplicate data detection (identical entries across different steps)
- No pre-signed blank pages
- Contemporaneous recording indicators
- Attributable entries (who did what, when)

**L5 — Data Intelligence (Hybrid)**
- CPP values within specified ranges
- IPC results within acceptance criteria
- Yield within expected range (typically 90-110% of theoretical)
- Material balance calculations correct
- Environmental monitoring within limits

**L6 — Cross-Reference Traceability (LLM, Dossier-Enhanced)**
- Deviation references in BPR match actual deviation documents in dossier
- CAPA references traceable to real CAPAs
- Equipment IDs match equipment logs
- Raw material lot numbers traceable to COAs
- Cleaning validation references current

**L7 — Lifecycle / Timeliness (Rule Engine)**
- Batch review completed within defined timeframe (typically 30 days)
- All deviations closed before release
- No open action items at time of release
- Reprocessing properly documented if applicable
- Yield check performed at appropriate stage

**L8 — Regulatory Compliance (LLM with RAG)**
- 21 CFR 211.186 (MBR requirements) compliance
- 21 CFR 211.188 (BPR requirements) compliance
- 21 CFR 211.192 (production record review) compliance
- 21 CFR Part 11 (electronic records) if applicable
- EU GMP Chapter 4 / Annex 11 if applicable
- ICH Q7 (API) or Q10 (PQS) alignment

**L9 — Enforcement Pattern Matching (Existing Engine)**
- Match findings against FDA 483 observations and warning letters
- 21 CFR 211.192 was cited 116 times in FY2024 — second most common 483 observation
- Severity elevation for patterns matching consent decree triggers

**L10 — Longitudinal Analysis (Existing Engine)**
- Compare batch record quality across lots for same product
- Detect recurring findings across batches
- Department and operator trending

**L11 — Inspectability (Rule Engine)**
- No TBD placeholders or draft language
- All pages accounted for
- Internal cross-section consistency (batch number matches throughout)
- Effective date present
- Version control complete

### 6.3 What Was Already Built (Needs Design Review)

In the prior session, 44 deterministic rule engine checks were implemented and 87 total checks were defined in DTAP-007. These were built before this architecture discussion and should be reviewed against this proposal before being considered final. The code exists in:
- `app/dtap/profiles/mbr.py` — DTAP-007 profile definition
- `app/engines/rule_engine.py` — Rule engine check implementations (end of file)
- `app/dtap/registry.py` — MBR registered in DTAPRegistry

---

## 7. Finding Model

### 7.1 Existing Finding Model (Already Built)

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

### 7.2 What ChatGPT Proposed vs. What Exists

ChatGPT's proposal suggested creating a new `MBRFinding` model with fields like severity, category, description, source_page, section, expected, observed, confidence, human_verification_required, recommended_reviewer_action, status, reviewer_rationale.

**This is unnecessary.** The existing `Finding` model already covers all of these fields, and in most cases with more depth (enforcement matching, citation types, remediation priority). Creating a separate MBR-specific finding model would break Clyira's architecture — all document types produce the same `Finding` entity, enabling cross-document comparison, longitudinal analysis, and consistent scoring.

### 7.3 Additions Needed for MBR Context

Two fields could be added to the existing `Finding` model (or stored in a JSONB metadata column):

- **source_page** (Integer, nullable) — Page number where the finding was detected. Currently, findings have `location` (section name) but not page number. This is valuable for batch records where reviewers flip to specific pages.
- **human_verification_required** (Boolean, default False) — Flag for findings where the underlying data came from OCR extraction with low confidence, or where the check involves a critical parameter that regulatory guidance requires human verification.

These can be added as nullable columns in a future migration without breaking existing functionality.

---

## 8. Human Review Controls

### 8.1 Existing Review Workflow

Clyira already has a finding status workflow in the `Finding` model:
- **open** → Finding detected, awaiting review
- **acknowledged** → Reviewer has seen and agrees
- **in_progress** → Remediation underway
- **resolved** → Fixed, with evidence/rationale
- **disputed** → Reviewer disagrees, with documented reason

The scoring engine respects these states: resolved findings have 0x deduction weight, in_progress has 0.5x, open/disputed have full 1.0x weight.

### 8.2 MBR-Specific Review Controls (New)

For batch record review, stricter controls are needed:

**Dismiss-all prevention:** A "dismiss all" button must not exist. Each finding must be individually addressed with rationale.

**Critical finding escalation:** Critical and high severity findings cannot be dismissed without documented rationale of at least 50 characters. Dismissals of critical findings should trigger notification to QA Approver.

**Human verification queue:** Findings flagged with `human_verification_required = True` (from OCR confidence or critical parameter checks) must be explicitly verified by a human before the dossier can move to disposition.

**SME assignment:** A finding can be assigned to a specific user (Manufacturing Reviewer, QC Reviewer) for domain-specific response. The `actioned_by` field on Finding already supports tracking who took action.

**Escalation to QA Approver:** Any reviewer can escalate a finding to the QA Approver if they cannot make a determination. This adds the finding to the Approver's review queue.

**Correction workflow:** When a reviewer corrects an extracted value (e.g., OCR misread "5.2" as "52"), the correction is stored as a `FeedbackCorrection` record linking the original value, corrected value, finding ID, and source coordinates. This serves as training data for future extraction improvement.

### 8.3 Implementation Approach

Most of this is handled through the existing `Finding.status` and `Finding.response_text` fields plus UI logic. The only new data needed is:

- `FeedbackCorrection` model (new table) — for storing value corrections
- Business logic in the router layer to enforce dismissal rules (minimum rationale length, escalation triggers)
- UI changes to the finding card component to support assignment and verification workflows

---

## 9. Data Model Proposal

### 9.1 New Entities Required

**NOTE: These are proposed interfaces only. No implementation yet.**

#### BatchDossier (New Model)

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
├── status: String [draft, under_review, pending_disposition, released, rejected, on_hold]
├── disposition_score: Float (nullable) — composite of individual doc scores
├── disposition_band: String (nullable) — Excellent/Good/Moderate/Poor/Critical
├── disposition_recommendation: String (nullable) — AI-generated, human-verified
├── gate_open_deviations: Boolean (default True) — blocks if open deviations exist
├── gate_open_capas: Boolean (default True) — blocks if open CAPAs exist
├── gate_qc_complete: Boolean (default False) — all QC results linked and passing
├── gate_data_integrity: Boolean (default True) — blocks if any DI hold on any document
├── gate_all_findings_addressed: Boolean (default False) — all critical/high findings resolved
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
├── confidence_score: Float (nullable) — original extraction confidence
├── correction_rationale: Text (nullable)
├── created_at: DateTime
```

### 9.2 Existing Entities That Stay Unchanged

The following models are NOT modified — the MBR module uses them as-is:

- **Document** — BPR and supporting documents are regular Document records
- **Assessment** — Each document assessment uses the existing Assessment model
- **Finding** — All findings (MBR and otherwise) use the existing Finding model
- **Company** — Multi-tenant root, unchanged
- **User** — Role-based access, unchanged
- **Audit** — Audit trail, unchanged
- **DocumentReference** — Supporting documents can also use this existing mechanism
- **EnforcementRecord** — Enforcement matching is the same pipeline
- **RegulatoryCorpus** — Regulatory knowledge base, unchanged

### 9.3 Entities NOT Needed (Correcting ChatGPT's Proposal)

ChatGPT proposed these entities which are NOT required because they duplicate existing Clyira functionality:

- **MBRReviewJob** — This is the existing `Assessment` model. Clyira already has job queuing (status: queued → running → completed → failed), Celery background tasks, and progress tracking.
- **UploadedBatchFile** — This is the existing `Document` model. Documents are already stored with file_path, file_type, extracted_text, extracted_sections.
- **BatchRecordSection** — This is already captured in `Document.extracted_sections` (JSONB). No separate table needed.
- **ExtractedField** — Not needed in Phase 1. Future OCR work may justify this, but it should be a JSONB field on Document or a lightweight model, not a full entity at this stage.
- **MBRFinding** — This is the existing `Finding` model. All assessment findings are the same entity.
- **ReviewerAction** — This is already captured in `Finding.status`, `Finding.response_text`, `Finding.actioned_by`, and the `Audit` log.
- **HumanVerificationItem** — This is a filtered view of findings where `human_verification_required = True`. No separate entity needed.
- **ReviewReport** — This is a generated export (PDF/DOCX), not a stored entity. The data comes from the dossier + assessments + findings.
- **ProcessingAuditLog** — This is the existing `Audit` model.

The point is not that these concepts are wrong — they're valid. But Clyira already implements most of them, and creating parallel models would fragment the data and break the platform's consistency.

---

## 10. UI Proposal

### 10.1 Existing UI Architecture

Clyira's frontend is built with Next.js 14+ (App Router), React, TailwindCSS, TypeScript. The dashboard uses a `(dashboard)/` route group with pages for documents, assessments, readiness, inspections, evidence, audit, and settings.

### 10.2 New Screens Required

#### Batch Dossiers List — `/(dashboard)/batch-dossiers/page.tsx`
Table showing all batch dossiers for the company. Columns: lot number, product, status, disposition score, gate status (icons), manufacturing date, created by. Filters by status, product, date range.

#### New Batch Dossier — `/(dashboard)/batch-dossiers/new/page.tsx`
Form to create a dossier: lot number, product name, product code, manufacturing date, manufacturing site. Upload primary BPR and optionally attach supporting documents.

#### Dossier Dashboard — `/(dashboard)/batch-dossiers/[id]/page.tsx`
The core screen. Layout:
- **Header:** Lot number, product, status badge, composite disposition score with band
- **Gate Status Panel:** Visual checklist of release gates (green/red/amber icons)
  - All deviations closed
  - All CAPAs effective
  - QC results complete and passing
  - No data integrity holds
  - All critical/high findings addressed
- **Documents Panel:** Cards for each linked document showing: title, type, individual Clyira score, finding count by severity, assessment status
- **Findings Summary:** Aggregated findings across all documents in the dossier, grouped by severity, filterable by document and level
- **Timeline:** Chronological view of all actions taken on the dossier

#### Document Viewer (Enhanced) — `/(dashboard)/batch-dossiers/[id]/documents/[docId]/page.tsx`
Extends the existing document detail page with:
- Side-by-side view: original document (PDF render) on left, findings on right
- Click a finding to highlight the relevant section/page in the document
- Human verification queue for OCR-extracted values (future)

#### Review Report Export — Modal or dedicated page
Generate and download the audit-ready review report. Includes: dossier summary, all findings with reviewer actions and rationale, disposition recommendation, signatures.

### 10.3 Modifications to Existing Screens

- **Documents List:** Add "Batch Dossier" column showing which dossier (if any) a document belongs to
- **Dashboard:** Add "Batch Dossiers" card showing recent dossiers and their status
- **Navigation:** Add "Batch Review" item to sidebar navigation

---

## 11. Phased Implementation Options

### Option 1: Architecture Document Only

**What would be built:** This document. No code changes.
**What would not be built:** Everything else.
**Complexity:** None.
**Risks:** Analysis paralysis — valuable if the team needs alignment, wasteful if the direction is already clear.
**Best use case:** Team alignment before committing engineering resources.
**Why choose:** Need stakeholder buy-in. Want to share with advisors or investors.
**Why avoid:** Direction is already decided and time is better spent building.

### Option 2: DTAP-007 Review + Auto-Classify Fix (Quick Win)

**What would be built:** Review the already-built DTAP-007 profile and rule engine checks against this architecture proposal. Fix the `_auto_classify()` gap so MBR documents are recognized. Verify integration works end-to-end with a test document.
**What would not be built:** Batch Dossier, QC Test Record DTAP, new UI screens, OCR.
**Complexity:** Low (1-2 weeks).
**Risks:** Delivers single-document MBR assessment only. No lot-level view. But it's shippable.
**Best use case:** Want something working immediately while planning the full dossier.
**Why choose:** Proves the DTAP works, catches early design issues, gives customers something to react to.
**Why avoid:** Incomplete value proposition — customers want lot-level view, not just single doc assessment.

### Option 3: Batch Dossier MVP

**What would be built:** BatchDossier model + migration, BatchDispositionService, dossier API routes, dossier UI (list + dashboard + document linking), auto-classify fix, DTAP-007 review.
**What would not be built:** QC Test Record DTAP, OCR/handwriting, MBR template mapping, review memo generation, feedback corrections.
**Complexity:** Medium (4-6 weeks).
**Risks:** No QC data integration yet — dossier gates for QC would be manual. Template variability not addressed (relies on existing text extraction).
**Best use case:** Want the full lot-level value proposition without OCR complexity.
**Why choose:** This is the differentiated product — no competitor offers lot-level cross-document batch review. Delivers real value for companies with digital/eBR records.
**Why avoid:** If target customers are primarily paper-based, they need OCR before the dossier is useful.

### Option 4: Batch Dossier + QC Test Record DTAP

**What would be built:** Everything in Option 3 plus DTAP-008 (QC Test Record / COA assessment), making the QC gate in the dossier functional with automated assessment.
**What would not be built:** OCR/handwriting, MBR template mapping, review memo generation.
**Complexity:** Medium-High (6-8 weeks).
**Risks:** Larger scope but still no OCR. Two new DTAPs to validate.
**Best use case:** Want the complete batch release readiness picture including QC data.
**Why choose:** Completes the "360-degree batch disposition" vision for digital-first customers.
**Why avoid:** Scope creep risk if both DTAPs need extensive iteration.

### Option 5: Defer MBR, Build QC Test Record First

**What would be built:** DTAP-008 for QC test records, COA assessment checks, integration with existing assessment pipeline. No MBR, no dossier.
**What would not be built:** Everything MBR-related.
**Complexity:** Low-Medium (2-3 weeks).
**Risks:** Doesn't deliver the MBR value proposition. But QC test records are simpler (more structured, less handwriting, fewer template variations) and may be a better starting point.
**Best use case:** If market research shows QC test record review is a more pressing pain point, or if MBR complexity feels premature.
**Why choose:** Lower risk, faster delivery, validates the pipeline extension pattern before tackling the harder MBR problem.
**Why avoid:** Doesn't address the original product vision of MBR review.

### Option 6: Phase 1 Mock UI + Architecture

**What would be built:** Clickable prototype/mockup of the dossier UI workflow (upload → review → findings → disposition), plus this architecture document.
**What would not be built:** Backend, assessment pipeline, database models.
**Complexity:** Low (1-2 weeks).
**Risks:** No working product. But useful for investor demos, customer validation, and team alignment.
**Best use case:** Want to validate the UX with potential customers before building backend.
**Why choose:** De-risks the UI/UX before committing to 6+ weeks of backend work.
**Why avoid:** If the product direction is already validated and speed-to-market matters more than UX polish.

---

## 12. Risks and Open Questions

### 12.1 Technical Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Handwriting accuracy** | High | Phase in cautiously. Never rely on OCR for critical decisions. Always require human verification. See Section 5. |
| **Scan quality** | Medium | Accept digital PDFs first. Add scan quality scoring in Phase 2. Reject illegible scans with clear messaging. |
| **Template variability** | High | Every company (and every CMO) uses different batch record templates. Clyira's DTAP approach is template-agnostic (assesses content, not layout), but section identification will struggle with unfamiliar formats. LLM fallback helps here. |
| **Page boundary loss** | Medium | Current pdfplumber extraction concatenates pages. Need to preserve page numbers for evidence linking. This is a code change in `_extract_text_from_bytes()`. |
| **Validation burden** | High | Any AI tool used in GMP context should be validated per GAMP 5 / FDA guidance. Clyira's anti-hallucination gate, tamper-evident hashing, and audit trail support validation, but customers will need to validate within their own quality system. |
| **False negatives** | Medium | More dangerous than false positives — a missed critical finding could lead to releasing a deficient batch. Mitigation: conservative thresholds, human verification requirements, clear disclaimer that Clyira supplements but does not replace human review. |
| **LLM cost scaling** | Low | Batch records can be very long (100+ pages). Current Groq free tier (14,400 req/day) may be strained. Consider chunking strategy for long documents. |

### 12.2 Product Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Reviewer overreliance on AI** | High | This is the Purolea risk. Mitigation: never auto-approve, require human verification for critical findings, include prominent disclaimers, design UI to encourage engagement (not rubber-stamping). |
| **Confusion with batch release** | High | Customers may expect Clyira to "release" batches. Clear product positioning: Clyira supports review, humans make decisions. UI must never have a "Release Batch" button that bypasses human judgment. |
| **Scope creep toward MES** | Medium | The Batch Dossier concept could expand toward full manufacturing execution. Maintain clear boundary: Clyira is post-hoc review, not execution. |
| **Integration complexity** | Medium | Customers will want Clyira to pull data from their MES, LIMS, ERP. Initial version requires manual upload. API integrations are Phase 2+. |
| **Market timing** | Low | FDA's increasing focus on AI in pharma (Purolea letter, AI Guiding Principles) creates both opportunity (demand for responsible AI tools) and risk (regulatory scrutiny). |

### 12.3 Open Questions for Product Owner

1. **Target customer profile:** Companies with digital eBR exports? Paper-based? Both? This determines whether OCR is Phase 1 or Phase 3.

2. **Dossier vs. single document priority:** Should the dossier concept be built first (more differentiated) or should single-document MBR assessment ship first (faster, lower risk)?

3. **QC Test Record timing:** Build alongside MBR or separately? The dossier value proposition is stronger with both.

4. **CMO scenario priority:** Virtual pharma companies receiving batch records from multiple CMOs is a strong use case. Does the module need CMO-specific features (template mapping, multi-format handling) in the initial release?

5. **Review memo generation:** How important is generating a draft QA review memo vs. just presenting findings? This is additional LLM work but could be high-value.

6. **Pricing model:** Is this included in the existing Clyira subscription or an add-on module? This affects build priority and scope.

7. **Validation support:** Should Clyira provide validation documentation (IQ/OQ/PQ templates, test scripts) to help customers validate the module? This is a significant differentiator but adds documentation work.

---

## 13. Recommendation

Based on the analysis of the existing codebase, market research, regulatory landscape, and stress testing against real scenarios:

**Recommended path is Option 3 (Batch Dossier MVP), with Option 2 as a quick preliminary step to validate the DTAP-007 pipeline works end-to-end.**

The reasoning:

- The Batch Dossier is Clyira's unique differentiator. No competitor offers lot-level, cross-document batch review. Acodis does single-document extraction. Tulip/Apprentice do execution. Clyira can own the "review intelligence" layer.

- The existing architecture supports this cleanly. The dossier is a layer on top of the current pipeline — it doesn't require changes to the assessment orchestrator, rule engine, scoring engine, or any existing DTAP.

- OCR is explicitly Phase 2+. Starting with digital PDFs and eBR exports covers the growing EBR market without the risk and complexity of handwriting recognition.

- The DTAP-007 profile and 44 rule engine checks already built in the prior session provide a head start, but should be reviewed against this architecture document before shipping.

**However, final decision should be made by the product owner** based on customer feedback, market timing, and resource availability.

---

## 14. Appendix: Codebase Inventory

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
| `app/models/assessment.py` | Minor additions possible | source_page, human_verification_required fields |
| `app/models/document.py` | No changes needed | BPRs are regular documents |

### Files That Need to Be Created

| File | Purpose |
|---|---|
| `app/models/batch_dossier.py` | BatchDossier and BatchDossierDocument models |
| `app/models/feedback_correction.py` | FeedbackCorrection model |
| `app/services/batch_disposition_service.py` | Dossier aggregation, gate logic, disposition scoring |
| `app/routers/batch_dossiers.py` | API endpoints for dossier CRUD and disposition |
| `app/schemas/batch_dossier.py` | Pydantic request/response schemas |
| `alembic/versions/xxx_add_batch_dossiers.py` | Database migration |
| `apps/web/src/app/(dashboard)/batch-dossiers/` | Frontend pages (list, new, detail) |

### Capabilities That Do NOT Exist in the Codebase

For accuracy, the following capabilities referenced in various proposals do NOT currently exist in Clyira and should not be assumed:

- OCR / Tesseract / handwriting recognition — NOT built
- Image-based field extraction — NOT built
- Page boundary preservation in text extraction — NOT built
- Scan quality assessment — NOT built
- Missing/duplicate page detection — NOT built
- MBR template comparison (master vs. executed) — NOT built
- CPP/IPC range validation against specifications — NOT built (checks exist in DTAP but are LLM-fallback, not rule-based with actual spec values)
- LIMS / MES / ERP integration — NOT built
- COA generation — NOT built
- Handwriting zone detection — NOT built

---

**END OF ARCHITECTURE PROPOSAL**

*This document should be reviewed by the product owner before any implementation begins. All technical claims about the codebase have been verified against the actual source code as of May 27, 2026.*
