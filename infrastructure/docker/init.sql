-- Clyira Database Initialization
-- PostgreSQL 16 with pgvector extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- CORE TABLES: Multi-tenancy & Authentication
-- ============================================================

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    -- Onboarding configuration
    sub_sectors JSONB NOT NULL DEFAULT '[]',        -- Array of SS-codes (SS-D1, SS-B5, etc.)
    agencies JSONB NOT NULL DEFAULT '[]',           -- Selected regulatory agencies
    markets JSONB NOT NULL DEFAULT '[]',            -- Target markets (US, EU, Japan, etc.)
    certifications JSONB DEFAULT '[]',              -- ISO 13485, AABB, CAP, etc.
    -- Settings
    settings JSONB DEFAULT '{}',
    onboarding_complete BOOLEAN DEFAULT FALSE,
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'author',     -- admin, qa_lead, author, reviewer, approver, auditor, sme
    department VARCHAR(100),                         -- Free-text, maps to standard taxonomy
    department_code VARCHAR(10),                     -- Standard dept code (QA, QC, MFG, etc.)
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(email, company_id)
);

CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- DOCUMENT MANAGEMENT
-- ============================================================

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    -- Document identity
    title VARCHAR(500) NOT NULL,
    document_number VARCHAR(100),
    version VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'uploaded',  -- uploaded, classifying, assessed, reviewing, approved, archived
    -- 3-Dimension Classification
    function_type VARCHAR(10),                       -- POL, SOP, WI, SPEC, PROTO, RPT, etc.
    regulatory_category VARCHAR(10),                 -- GMP, GCP, GLP, GDP, etc.
    department_owner VARCHAR(10),                    -- QA, QC, MFG, VAL, etc.
    -- DTAP assignment
    dtap_code VARCHAR(20),                          -- DTAP-001, DTAP-002, etc.
    criticality_tier VARCHAR(5),                    -- T1, T2, T3
    -- File storage
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_size BIGINT,
    file_type VARCHAR(50),                          -- pdf, docx, xlsx
    -- Extracted content
    extracted_text TEXT,
    sections JSONB,                                  -- Detected section structure
    metadata JSONB DEFAULT '{}',                     -- Additional extracted metadata
    -- Lifecycle
    effective_date DATE,
    review_date DATE,
    superseded_by UUID REFERENCES documents(id),
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documents_company ON documents(company_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_dtap ON documents(dtap_code);
CREATE INDEX idx_documents_function ON documents(function_type);
CREATE INDEX idx_documents_dept ON documents(department_owner);

-- User-uploaded organizational references for assessment
CREATE TABLE document_references (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    -- Reference details
    title VARCHAR(500),
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    reference_type VARCHAR(50) NOT NULL,             -- internal_sop, quality_manual, quality_agreement, prior_483_response, organizational_guideline, checklist, other
    description TEXT,
    extracted_text TEXT,
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_doc_refs_document ON document_references(document_id);
CREATE INDEX idx_doc_refs_company ON document_references(company_id);

-- ============================================================
-- ASSESSMENT ENGINE
-- ============================================================

CREATE TABLE assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    initiated_by UUID NOT NULL REFERENCES users(id),
    -- Assessment configuration
    agencies_assessed JSONB NOT NULL DEFAULT '[]',   -- Which agencies were assessed against
    dtap_code VARCHAR(20) NOT NULL,
    assessment_version INTEGER NOT NULL DEFAULT 1,
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'queued',    -- queued, in_progress, completed, failed, suspended
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    -- Results
    clyira_score DECIMAL(5,2),                       -- 0.00 to 100.00
    score_band VARCHAR(20),                          -- e.g., "High", "Moderate", "Low", "Critical Gap"
    score_suspended BOOLEAN DEFAULT FALSE,           -- True if Critical L4 finding
    suspension_reason TEXT,
    -- Finding counts
    findings_critical INTEGER DEFAULT 0,
    findings_major INTEGER DEFAULT 0,
    findings_minor INTEGER DEFAULT 0,
    findings_observation INTEGER DEFAULT 0,
    findings_ambiguous INTEGER DEFAULT 0,
    -- Enforcement matches
    enforcement_matches INTEGER DEFAULT 0,
    -- References used
    references_used JSONB DEFAULT '[]',              -- IDs of document_references included
    -- Metadata
    processing_time_ms INTEGER,
    llm_tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assessments_document ON assessments(document_id);
CREATE INDEX idx_assessments_company ON assessments(company_id);
CREATE INDEX idx_assessments_status ON assessments(status);

CREATE TABLE findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Finding classification
    level VARCHAR(5) NOT NULL,                       -- L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11
    severity VARCHAR(20) NOT NULL,                   -- critical, major, minor, observation
    original_severity VARCHAR(20),                   -- Before L9/L10 elevation
    elevated_by VARCHAR(5),                          -- L9 or L10 if elevated
    category VARCHAR(50),                            -- e.g., "structural_missing_section", "data_integrity_gap", etc.
    -- Finding content
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    section_reference VARCHAR(200),                   -- Which document section
    -- Regulatory basis
    regulatory_citation TEXT,                         -- e.g., "21 CFR 211.192"
    regulatory_hierarchy_level INTEGER,              -- 0-6 (Internal to Enforcement)
    guidance_reference TEXT,
    basis_type VARCHAR(50),                          -- direct_regulatory, guidance, good_practice, inspection_pattern, expert_derived
    -- Enforcement context (if L9 match)
    enforcement_match BOOLEAN DEFAULT FALSE,
    enforcement_source VARCHAR(50),                   -- warning_letter, 483, eir, etc.
    enforcement_agency VARCHAR(50),
    enforcement_date DATE,
    enforcement_excerpt TEXT,                         -- Anonymized
    enforcement_severity_outcome VARCHAR(100),
    -- Remediation
    suggestion_draft TEXT,                            -- AI-authored corrective content (editable doc types)
    next_step_text TEXT,                              -- User-entered commitment (locked doc types)
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'open',      -- open, accepted, disputed, resolved, escalated
    is_ambiguous BOOLEAN DEFAULT FALSE,              -- "Possible issues — requires expert review"
    confidence VARCHAR(20),                          -- high, medium, low
    -- User actions
    user_response TEXT,
    responded_by UUID REFERENCES users(id),
    responded_at TIMESTAMPTZ,
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_findings_assessment ON findings(assessment_id);
CREATE INDEX idx_findings_document ON findings(document_id);
CREATE INDEX idx_findings_company ON findings(company_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_level ON findings(level);
CREATE INDEX idx_findings_status ON findings(status);

-- ============================================================
-- REGULATORY CORPUS & ENFORCEMENT
-- ============================================================

CREATE TABLE regulatory_corpus (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Source identification
    source_type VARCHAR(50) NOT NULL,                -- ecfr, fda_guidance, ich_guideline, eu_gmp, pics, etc.
    agency VARCHAR(50),                              -- FDA, EMA, MHRA, PMDA, etc.
    -- Content
    title VARCHAR(1000) NOT NULL,
    section_id VARCHAR(200),                         -- e.g., "21 CFR 211.192" or "ICH Q10 Section 2"
    content TEXT NOT NULL,
    -- Classification
    regulatory_category VARCHAR(10),                 -- GMP, GCP, GLP, etc.
    applicable_sub_sectors JSONB DEFAULT '[]',
    applicable_document_types JSONB DEFAULT '[]',
    hierarchy_level INTEGER NOT NULL,                -- 1-5 (Statutory to Pharmacopoeia)
    -- Embedding for RAG
    embedding vector(1536),
    -- Metadata
    effective_date DATE,
    superseded_date DATE,
    source_url TEXT,
    last_refreshed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_corpus_source ON regulatory_corpus(source_type);
CREATE INDEX idx_corpus_agency ON regulatory_corpus(agency);
CREATE INDEX idx_corpus_category ON regulatory_corpus(regulatory_category);
CREATE INDEX idx_corpus_embedding ON regulatory_corpus USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE enforcement_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Source identification
    source_type VARCHAR(50) NOT NULL,                -- warning_letter, 483, eir, oai, import_alert, consent_decree, recall, doj, non_compliance
    agency VARCHAR(50) NOT NULL,                     -- FDA, EMA, MHRA, Health_Canada, TGA, etc.
    -- Content
    date_issued DATE NOT NULL,
    company_name_internal VARCHAR(500),              -- Stored but NEVER shown to users
    facility_id VARCHAR(100),                        -- FEI number (FDA) or equivalent
    product_type VARCHAR(100),
    sub_sector_code VARCHAR(10),                     -- Mapped to Clyira SS codes
    observation_text TEXT NOT NULL,
    regulatory_citation TEXT,
    -- Classification
    document_types_affected JSONB DEFAULT '[]',      -- Mapped to Clyira document types
    pattern_tags JSONB DEFAULT '[]',                 -- e.g., ["oos_investigation", "data_integrity", "cleaning_validation"]
    severity_outcome VARCHAR(100),                   -- observation_only, warning_letter, consent_decree, import_alert, recall, doj_action
    inspection_classification VARCHAR(10),           -- OAI, VAI, NAI (FDA only)
    repeat_flag BOOLEAN DEFAULT FALSE,
    -- Embedding for pattern matching
    embedding vector(1536),
    -- Metadata
    source_url TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_valid BOOLEAN DEFAULT TRUE,                   -- False if cited regulation superseded
    last_validated TIMESTAMPTZ
);

CREATE INDEX idx_enforcement_agency ON enforcement_records(agency);
CREATE INDEX idx_enforcement_source ON enforcement_records(source_type);
CREATE INDEX idx_enforcement_sub_sector ON enforcement_records(sub_sector_code);
CREATE INDEX idx_enforcement_date ON enforcement_records(date_issued);
CREATE INDEX idx_enforcement_tags ON enforcement_records USING gin(pattern_tags);
CREATE INDEX idx_enforcement_embedding ON enforcement_records USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- COMPANY LEVEL 0 (Internal Standards)
-- ============================================================

CREATE TABLE company_references (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    -- Reference type
    reference_type VARCHAR(50) NOT NULL,             -- sop, quality_manual, quality_agreement, regulatory_submission, prior_483_response, validated_method
    title VARCHAR(500) NOT NULL,
    document_number VARCHAR(100),
    version VARCHAR(50),
    -- Content
    file_path VARCHAR(1000),
    file_name VARCHAR(500),
    extracted_text TEXT,
    sections JSONB,
    -- Embedding
    embedding vector(1536),
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_company_refs_company ON company_references(company_id);
CREATE INDEX idx_company_refs_type ON company_references(reference_type);
CREATE INDEX idx_company_refs_embedding ON company_references USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- ============================================================
-- AUDIT READINESS (Module 2)
-- ============================================================

CREATE TABLE readiness_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Score hierarchy
    scope_type VARCHAR(20) NOT NULL,                 -- document, department, company
    scope_id VARCHAR(100),                           -- department_code or NULL for company
    -- Score
    score DECIMAL(5,2) NOT NULL,
    score_band VARCHAR(20),
    -- Breakdown
    findings_summary JSONB DEFAULT '{}',
    trend_data JSONB DEFAULT '[]',                   -- Historical scores for trend
    -- Timestamp
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_readiness_company ON readiness_scores(company_id);
CREATE INDEX idx_readiness_scope ON readiness_scores(scope_type, scope_id);

CREATE TABLE inspection_simulations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    -- Configuration
    simulation_type VARCHAR(50) NOT NULL,            -- mock_inspection, scenario, question_set
    title VARCHAR(500),
    target_departments JSONB DEFAULT '[]',
    -- Content
    questions JSONB DEFAULT '[]',
    findings_predicted JSONB DEFAULT '[]',
    -- Status
    status VARCHAR(50) DEFAULT 'created',            -- created, in_progress, completed
    score DECIMAL(5,2),
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ============================================================
-- REAL-TIME AUDIT SUPPORT (Module 3)
-- ============================================================

CREATE TABLE inspections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    -- Inspection details
    title VARCHAR(500) NOT NULL,
    agency VARCHAR(50),
    inspection_type VARCHAR(100),                    -- routine, for_cause, pre_approval, surveillance
    start_date DATE,
    end_date DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'planned',   -- planned, active, post_inspection, closed
    -- Team assignments
    team_assignments JSONB DEFAULT '{}',             -- {role: user_id} mapping
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inspections_company ON inspections(company_id);
CREATE INDEX idx_inspections_status ON inspections(status);

CREATE TABLE inspection_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Request details
    request_text TEXT NOT NULL,
    criticality VARCHAR(20) NOT NULL DEFAULT 'medium', -- critical, high, medium, low
    category VARCHAR(100),                            -- document_request, question, observation, commitment
    -- Assignment
    assigned_to UUID REFERENCES users(id),
    status VARCHAR(50) NOT NULL DEFAULT 'open',       -- open, assigned, in_progress, ready_for_review, delivered, closed
    -- Response
    response_text TEXT,
    response_documents JSONB DEFAULT '[]',            -- Document IDs attached to response
    -- Timing
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_by TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    -- AI assistance
    ai_suggested_response TEXT,
    ai_suggested_documents JSONB DEFAULT '[]',
    ai_talking_points JSONB DEFAULT '[]'
);

CREATE INDEX idx_requests_inspection ON inspection_requests(inspection_id);
CREATE INDEX idx_requests_status ON inspection_requests(status);
CREATE INDEX idx_requests_assigned ON inspection_requests(assigned_to);

CREATE TABLE inspection_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id UUID NOT NULL REFERENCES inspections(id) ON DELETE CASCADE,
    -- Log entry
    entry_type VARCHAR(50) NOT NULL,                  -- scribe_note, observation, question, commitment, action_item
    content TEXT NOT NULL,
    tags JSONB DEFAULT '[]',
    -- Attribution
    logged_by UUID REFERENCES users(id),
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_log_inspection ON inspection_log(inspection_id);

-- ============================================================
-- DOCUMENT WORKFLOW (Review & Approval)
-- ============================================================

CREATE TABLE document_workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    -- Workflow state
    stage VARCHAR(50) NOT NULL DEFAULT 'draft',       -- draft, in_review, approved, rejected, archived
    current_step INTEGER DEFAULT 1,
    -- Participants
    author_id UUID NOT NULL REFERENCES users(id),
    reviewers JSONB DEFAULT '[]',                     -- [{user_id, status, reviewed_at, comments}]
    approvers JSONB DEFAULT '[]',                     -- [{user_id, status, approved_at, comments}]
    -- Timestamps
    submitted_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- AUDIT TRAIL (21 CFR Part 11 aligned)
-- ============================================================

CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID REFERENCES users(id),
    -- Event
    action VARCHAR(100) NOT NULL,                     -- document_uploaded, assessment_started, finding_disputed, etc.
    entity_type VARCHAR(50) NOT NULL,                 -- document, assessment, finding, user, company, inspection
    entity_id UUID NOT NULL,
    -- Details
    details JSONB DEFAULT '{}',
    previous_state JSONB,
    new_state JSONB,
    -- Context
    ip_address INET,
    user_agent TEXT,
    -- Timestamp (immutable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_company ON audit_trail(company_id);
CREATE INDEX idx_audit_entity ON audit_trail(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_trail(user_id);
CREATE INDEX idx_audit_time ON audit_trail(created_at);

-- Prevent any updates or deletes on audit_trail (immutable)
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit trail records cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_trail_immutable
    BEFORE UPDATE OR DELETE ON audit_trail
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();
