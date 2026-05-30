# Clyira Platform

## What This Is

Clyira is an AI-powered regulatory intelligence platform for pharmaceutical, biotech, and medical device companies. It provides real-time document assessment, audit readiness scoring, enforcement intelligence, and live inspection support — built for FDA, EMA, and ICH standards.

## Tech Stack

- **Backend**: FastAPI (Python), PostgreSQL 16 with pgvector, Redis 7, Celery workers, Alembic migrations
- **Frontend**: Next.js 14 (TypeScript/React), Tailwind CSS, lucide-react icons
- **Storage**: Supabase storage for documents
- **Deployment**: Docker Compose (dev), Render (production)

## Codebase Structure

```
clyira-platform/
├── apps/
│   ├── api/                        # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── core/               # Config, database, dependencies
│   │   │   ├── dtap/               # Document-Type Assessment Profiles
│   │   │   │   ├── profile.py      # Base DTAP profile class
│   │   │   │   ├── registry.py     # Profile registry/loader
│   │   │   │   └── profiles/       # Per-type profiles: SOP, CAPA, Deviation, LIR, Validation, ATM
│   │   │   ├── engines/            # L1-L11 Neuro-Symbolic Assessment Engine
│   │   │   │   ├── orchestrator.py # Orchestrates all engine layers
│   │   │   │   ├── rule_engine.py  # Deterministic rule checks (L1,L2,L4,L5,L7,L11)
│   │   │   │   ├── llm_engine.py   # LLM semantic analysis via RAG (L3,L6,L8)
│   │   │   │   ├── rag_engine.py   # RAG retrieval engine
│   │   │   │   ├── enforcement_engine.py  # FDA enforcement pattern matching (L9)
│   │   │   │   ├── longitudinal_engine.py # Cross-document longitudinal analysis (L10)
│   │   │   │   ├── scoring.py      # Score aggregation and banding
│   │   │   │   ├── validator.py    # Anti-hallucination validation
│   │   │   │   └── types.py        # Shared types for engine results
│   │   │   ├── models/             # SQLAlchemy models (user, company, document, assessment, inspection, etc.)
│   │   │   ├── routers/            # API routes: auth, companies, documents, assessments, readiness, inspections, assistant, audit, notifications, api-keys, export
│   │   │   ├── schemas/            # Pydantic request/response schemas
│   │   │   ├── services/           # Business logic layer
│   │   │   ├── tasks/              # Celery background tasks
│   │   │   └── main.py             # FastAPI app + route registration
│   │   ├── alembic/                # Database migrations
│   │   ├── rag_index/              # JSONL indexes for RAG retrieval
│   │   │   ├── observations.jsonl  # 2,919 FDA Warning Letter observations
│   │   │   ├── failure_modes.jsonl # Failure mode library
│   │   │   └── regulatory_corpus.jsonl # Regulatory citations
│   │   ├── scripts/                # Data collection/processing scripts
│   │   ├── tests/                  # Golden answer tests
│   │   └── requirements.txt
│   └── web/                        # Next.js 14 frontend
│       ├── src/
│       │   ├── app/
│       │   │   ├── page.tsx        # Landing page
│       │   │   ├── layout.tsx      # Root layout
│       │   │   └── globals.css     # Global styles + clyira color tokens
│       │   ├── components/landing/ # Landing page components
│       │   │   ├── integrations-section.tsx  # Evidence Fabric + 60+ system integrations grid
│       │   │   ├── animate-in.tsx  # Scroll-triggered animation wrapper
│       │   │   ├── count-up.tsx    # Animated number counter
│       │   │   ├── marquee-strip.tsx # Auto-scrolling text strip
│       │   │   └── landing-nav.tsx # Top navigation
│       │   ├── hooks/              # Custom React hooks (use-auth.ts)
│       │   ├── lib/                # Utilities (api.ts, utils.ts)
│       │   └── middleware.ts       # Auth middleware
│       ├── tailwind.config.ts      # Custom colors (clyira-* purple palette)
│       └── package.json
├── infrastructure/
│   └── docker/
│       └── init.sql                # PostgreSQL schema with pgvector
├── docker-compose.yml              # PostgreSQL 16 + Redis 7
└── render.yaml                     # Render deployment config
```

## Key Domain Concepts

- **DTAP** (Document-Type Assessment Profile): The rule set applied to each document category. Current profiles: SOP, CAPA, Deviation, LIR (Lab Investigation Report), Validation, ATM (Analytical Test Method).
- **L1-L11 Assessment Levels**: The neuro-symbolic engine runs 11 checks per document — from structure/format (L1-L3) through regulatory alignment (L4-L6), risk/CAPA linkage (L7-L9), to enforcement actions and inspectability (L10-L11). Odd layers tend to be deterministic (rule_engine), even layers semantic (llm_engine).
- **Clyira Score**: A 0-100 composite score per document with bands: Critical (<50), Non-Compliant (50-69), Moderate (70-84), Compliant (85-100).
- **Enforcement Intelligence**: 2,919 FDA Warning Letter observations mapped to customer documents via RAG pattern matching.
- **Inspection Copilot**: Live support during FDA/EMA/PMDA inspections — log requests, get AI talking points, track outstanding items.

## Design System (Frontend)

- **Brand purple**: `clyira-600` (#7654c9) — defined in `tailwind.config.ts`
- **Dark sections**: `bg-[#0d0d0d]` with `border-white/10` cards
- **Light sections**: `bg-gray-50` or `bg-white`
- **Components**: Use `AnimateIn` wrapper for scroll-triggered entrance animations (props: `direction`, `delay`, `threshold`)
- **Icons**: lucide-react exclusively — never use other icon libraries
- **Typography**: System sans-serif stack, semibold for headings, `text-gray-900` primary / `text-gray-500` secondary

## Evidence Fabric Architecture (Planned Integration Layer)

This is the architectural plan for connecting Clyira to enterprise quality systems. The core insight: **don't build connectors first — prove the intelligence layer with CSV/Excel import + manual entity tagging, then add connectors when design partners demand them.**

### 7-Layer Architecture

1. **Universal Intake** — CSV/Excel upload, file storage connectors, future API push
2. **Evidence Object Store** — Normalized evidence objects with source, timestamp, hash, schema version
3. **Regulated Entity Registry** — Canonical registry of entities: equipment, personnel, material, method, sample, room, utility, system
4. **Quality Signals** — Events extracted from evidence: deviations, OOS, PM overdue, training gaps, EM excursions
5. **Document Claim Extraction** — NLP extraction of claims from documents (e.g., "root cause: analyst error") for cross-checking against evidence
6. **Compliance Control Map** — Expected controls per entity type mapped to regulatory requirements
7. **Clyira Findings + 360° Context** — Final assessment findings enriched with cross-system evidence

### Integration Timeline

- **MVP (Now)**: CSV/Excel import + file storage (SharePoint, Google Drive, Box, S3, SFTP) + manual entity tagging
- **Phase 2 (Months 3-6)**: QMS (Veeva Vault QMS, MasterControl, TrackWise) + EDMS + LIMS + CMMS
- **Phase 3 (Months 6-12)**: LMS + ELN + MES + ERP + EMS
- **Phase 4 (Year 2+)**: RIM + Pharmacovigilance + advanced connectors

### 13 Enterprise System Categories (60+ vendors)

The homepage (`integrations-section.tsx`) advertises all system categories:

1. **QMS/eQMS**: Veeva Vault QMS, MasterControl, TrackWise Digital, Qualio, ETQ Reliance, Dot Compliance, Greenlight Guru
2. **EDMS**: Veeva QualityDocs, MasterControl Docs, OpenText Documentum, SharePoint, Ennov Doc
3. **LIMS**: LabWare, STARLIMS, LabVantage, Veeva Vault LIMS, Sapio LIMS, SampleManager
4. **ERP**: SAP S/4HANA, Oracle NetSuite, Oracle Cloud ERP, Microsoft Dynamics 365, Infor CloudSuite
5. **MES**: Werum PAS-X, Rockwell PharmaSuite, Emerson Syncade, Siemens Opcenter, POMS, Tulip
6. **CMMS/EAM**: Blue Mountain RAM, IBM Maximo, SAP Plant Maintenance, eMaint, Limble CMMS
7. **LMS**: ComplianceWire, Veeva Vault Training, Cornerstone, MasterControl Training, Absorb
8. **EMS**: Vaisala viewLinc, MODA-EM, Particle Measuring Systems, Ellab, Rotronic
9. **ELN**: Benchling, IDBS E-WorkBook, Revvity Signals, Sapio ELN, Dotmatics
10. **RIM**: Veeva Vault RIM, ArisGlobal LifeSphere, EXTEDO EURS, Freyr iREADY
11. **File Storage**: SharePoint/OneDrive, Google Drive, Box, Dropbox Business, AWS S3, Azure Blob, SFTP
12. **Spreadsheets**: Excel/CSV, Google Sheets, Access databases, PDF forms, Paper (OCR)

### Reference Platforms Studied

- **TetraScience**: Scientific data cloud + harmonization layer — good model for data normalization
- **Scitara**: iPaaS for Science — connector library approach, pre-built adapters
- **Mareana**: Manufacturing intelligence — batch review AI, 21 CFR Part 11 compliance

### Key Architectural Principle

The product center is: **"Can this document's quality story be defended with evidence?"** — not "we connect to Veeva." The Evidence Fabric cross-references every document claim against evidence from across the entire quality ecosystem, finding gaps a document-only reviewer would miss.

## Sibling Project: Clyira-Corpus

The regulatory intelligence corpus lives at `~/Documents/Clyira - May 2026/Clyira-Corpus/`. See its own `CLAUDE.md` for details. Key facts:

- Contains enforcement data (2,858 FDA Warning Letters), regulations (21 CFR, EU GMP, ICH), guidance documents, failure mode libraries, ontologies, and RAG indexes
- The "moat" is sections 05-09: authored intelligence (failure modes, ontology, detection logic)
- Always read `CORPUS_BUILD_PLAN.md` before doing corpus work

## Rules for All Sessions

1. **Follow the design system** — Use clyira-* colors, lucide-react icons, AnimateIn wrappers. Never introduce new icon libraries or CSS frameworks.
2. **Backend conventions** — SQLAlchemy models in `models/`, Pydantic schemas in `schemas/`, business logic in `services/`, routes in `routers/`. Alembic for all schema changes.
3. **Assessment engine** — The orchestrator calls engines in L1-L11 order. Each engine returns typed `Finding` objects. Don't bypass the orchestrator.
4. **DTAP profiles** — One file per document type in `dtap/profiles/`. Each profile defines which assessment levels apply and their weights.
5. **RAG indexes** — JSONL format, one object per line. Stored in `rag_index/`. Scripts to rebuild go in `scripts/`.
6. **Evidence Fabric** — When building integration features, follow the 7-layer architecture above. Start with CSV/Excel intake, not enterprise connectors.
7. **Don't duplicate the corpus** — The `rag_index/` folder contains copies of corpus indexes. The source of truth is always `Clyira-Corpus/`.

## How to Handle My Instructions

I (Soumya) often give short, vague instructions. DO NOT just start coding from a vague instruction. Follow this protocol every time:

### Step 1: Clarify before acting

When I give a vague instruction, ALWAYS ask me 2-3 short clarifying questions before writing any code. Examples:

- "Fix the document page" → Ask: Which page? What's broken — layout, data, or functionality? What should it look like instead?
- "Add a feature" → Ask: Which part of the app? What should it do? Who uses it?
- "It's not working" → Ask: What did you expect to happen? What actually happened? Any error messages?
- "Make it better" → Ask: Better how — faster, prettier, more accurate? Which specific part?
- "Build this" (with screenshot) → Ask: Is this the exact design or a reference? What data powers it? Which existing components should I reuse?

Exception: If the instruction is already specific enough (e.g., "add a loading spinner to the assessment button in documents/[id]/page.tsx"), skip clarification and just do it.

### Step 2: Plan before coding

After clarifying, ALWAYS write a short plan listing:
1. Which files you'll read first
2. Which files you'll change or create
3. What the change does
4. What could break

Wait for my approval before coding, unless I say "just do it."

### Step 3: Verify after coding

After making changes, ALWAYS:
1. Re-read the changed files to confirm the edits are correct
2. Check for TypeScript errors if frontend: `npx tsc --noEmit`
3. Check for Python syntax errors if backend: `python -c "import ast; ast.parse(open('file').read())"`
4. Check that imports exist and are correct
5. Tell me what to test manually and what to look for

### Interpreting common short instructions

| What I say | What I mean |
|---|---|
| "check for bugs" / "review code" | Systematically read every file in the relevant layer. Check backend for: missing error handling, unvalidated inputs, missing auth, unhandled exceptions, race conditions, null checks, async/await issues, N+1 queries, hardcoded secrets, injection risks. Check frontend for: missing loading/error states, broken API calls, missing key props, useEffect leaks, type errors, missing form validation. Report each bug with file, line, severity, and fix. |
| "fix the UI" / "design looks wrong" | Check the component against the Design System section above. Look for wrong colors, wrong icons, layout overflow, missing responsive handling, missing states (loading/error/empty), broken Tailwind classes. |
| "it's broken" / "not working" | Don't guess. Ask me what I see vs what I expected. Then trace the full chain: frontend component → API call → router → service → engine/DB. Check console errors, network responses, and logs. |
| "deploy" / "push it" | Pre-deploy checklist: TypeScript errors, lint, missing env vars in render.yaml, uncommitted changes, TODO/FIXME in changed files. Then git add, commit with descriptive message, push. |
| "clean up" / "refactor" | Remove console.log/print, commented-out code, unused imports. Fix naming inconsistencies. Extract duplicated logic. Do NOT change functionality. |
| "make it production ready" | Run all of the above: bugs, tests, cleanup, deploy checks, in one pass. |
| "test it" | Run existing tests. If none exist for changed code, write them. Test happy path + error cases + edge cases. |
| "make it faster" / "optimize" | Profile first. Check for: unnecessary re-renders (React), N+1 queries, missing DB indexes, oversized API responses, missing caching, unoptimized images, bundle size. Report findings before changing anything. |
| "add a page/feature like X" | Read existing similar pages/features first to match patterns, naming conventions, and component structure. Reuse existing components — never build from scratch what already exists. |
| "the format is wrong" / "it changed the format" | This means the data transformation or rendering pipeline is altering the original content structure. Trace the data from source (upload/extraction) through storage to display (frontend rendering). Find where the structure changes and fix that specific point. Do NOT just change CSS — understand the root cause. |

### General principles

- **Read before writing** — always read a file before editing it
- **Don't touch what you weren't asked to touch** — avoid drive-by refactors
- **If changing the assessment engine** — verify the orchestrator still works end-to-end
- **If changing data extraction** — remember that old data in the DB won't retroactively change
- **If unsure** — ask, don't guess
- **Show me the plan** — I'd rather approve a plan than undo bad code
