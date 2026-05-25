"""Baseline schema — all tables as of initial deploy

Revision ID: 001_baseline
Revises:
Create Date: 2026-05-24 00:01

This is a BASELINE migration. The Clyira Render deployment already has
all these tables created via SQLAlchemy create_all(). Running this migration
on an existing database will be a no-op (all tables already exist).
On a fresh database, it creates the complete initial schema.

To apply:
    # Fresh DB:
    alembic upgrade head

    # Existing DB (mark as applied without running):
    alembic stamp 001_baseline
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"' )  # may fail on non-pgvector hosts; non-fatal

    # ── companies ──────────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("sub_sectors", postgresql.JSONB(), nullable=True),
        sa.Column("agencies", postgresql.JSONB(), nullable=True),
        sa.Column("markets", postgresql.JSONB(), nullable=True),
        sa.Column("certifications", postgresql.JSONB(), nullable=True),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=True),
        sa.Column("subscription_tier", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=True)

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("department_code", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_company_id", "users", ["company_id"])

    # ── documents ──────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.String(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("version", sa.String(20), nullable=True),
        sa.Column("effective_date", sa.String(20), nullable=True),
        sa.Column("function_type", sa.String(100), nullable=True),
        sa.Column("regulatory_category", sa.String(100), nullable=True),
        sa.Column("department_owner", sa.String(100), nullable=True),
        sa.Column("document_category", sa.String(50), nullable=True),
        sa.Column("regulatory_frameworks", postgresql.JSONB(), nullable=True),
        sa.Column("dtap_id", sa.String(50), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extracted_sections", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("latest_score", sa.Float(), nullable=True),
        sa.Column("latest_assessment_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("ix_documents_company_id", "documents", ["company_id"])

    # ── document_references ────────────────────────────────────────────────────
    op.create_table(
        "document_references",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("uploaded_by", sa.String(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("reference_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
    )

    # ── assessments ────────────────────────────────────────────────────────────
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("current_level", sa.String(20), nullable=True),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.Column("dtap_id", sa.String(50), nullable=True),
        sa.Column("levels_run", postgresql.JSONB(), nullable=True),
        sa.Column("include_references", sa.Boolean(), nullable=True),
        sa.Column("agencies_assessed", postgresql.JSONB(), nullable=True),
        sa.Column("clyira_score", sa.Float(), nullable=True),
        sa.Column("score_band", sa.String(20), nullable=True),
        sa.Column("findings_critical", sa.Integer(), nullable=True),
        sa.Column("findings_high", sa.Integer(), nullable=True),
        sa.Column("findings_medium", sa.Integer(), nullable=True),
        sa.Column("findings_low", sa.Integer(), nullable=True),
        sa.Column("findings_info", sa.Integer(), nullable=True),
        sa.Column("enforcement_matches", sa.Integer(), nullable=True),
        sa.Column("enforcement_details", postgresql.JSONB(), nullable=True),
        sa.Column("data_integrity_hold", sa.Boolean(), nullable=True),
        sa.Column("suspended_reason", sa.String(500), nullable=True),
        sa.Column("adjusted_score", sa.Float(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(50), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("ix_assessments_document_id", "assessments", ["document_id"])
    op.create_index("ix_assessments_company_id", "assessments", ["company_id"])
    op.create_index("ix_assessments_status", "assessments", ["status"])

    # ── findings ───────────────────────────────────────────────────────────────
    op.create_table(
        "findings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("assessment_id", sa.String(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("level_name", sa.String(100), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("regulatory_citation", sa.Text(), nullable=True),
        sa.Column("citation_type", sa.String(50), nullable=True),
        sa.Column("agency", sa.String(50), nullable=True),
        sa.Column("enforcement_match", sa.Boolean(), nullable=True),
        sa.Column("enforcement_record_id", sa.String(), nullable=True),
        sa.Column("enforcement_context", sa.Text(), nullable=True),
        sa.Column("severity_elevated", sa.Boolean(), nullable=True),
        sa.Column("suggestion_draft", sa.Text(), nullable=True),
        sa.Column("next_step_text", sa.Text(), nullable=True),
        sa.Column("remediation_priority", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("dispute_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.String(), nullable=True),
        sa.Column("actioned_by", sa.String(), nullable=True),
        sa.Column("validated", sa.Boolean(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"]),
    )
    op.create_index("ix_findings_assessment_id", "findings", ["assessment_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])

    # ── regulatory_corpus ──────────────────────────────────────────────────────
    op.create_table(
        "regulatory_corpus",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hierarchy_level", sa.Integer(), nullable=False),
        sa.Column("agency", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("citation_reference", sa.String(200), nullable=True),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.String(20), nullable=True),
        sa.Column("sub_sectors", postgresql.JSONB(), nullable=True),
        sa.Column("document_categories", postgresql.JSONB(), nullable=True),
        sa.Column("departments", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.Column("superseded_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_regulatory_corpus_citation", "regulatory_corpus", ["citation_reference"])
    op.create_index("ix_regulatory_corpus_agency", "regulatory_corpus", ["agency"])

    # ── failure_modes ──────────────────────────────────────────────────────────
    op.create_table(
        "failure_modes",
        sa.Column("id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("affected_companies_count", sa.Integer(), nullable=True),
        sa.Column("primary_cfr_citations", postgresql.JSONB(), nullable=True),
        sa.Column("observed_cfr_sections", postgresql.JSONB(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(), nullable=True),
        sa.Column("severity_range", postgresql.JSONB(), nullable=True),
        sa.Column("doc_categories", postgresql.JSONB(), nullable=True),
        sa.Column("sub_sectors", postgresql.JSONB(), nullable=True),
        sa.Column("root_cause_categories", postgresql.JSONB(), nullable=True),
        sa.Column("evidence_indicators", postgresql.JSONB(), nullable=True),
        sa.Column("example_observation_ids", postgresql.JSONB(), nullable=True),
        sa.Column("observation_years", postgresql.JSONB(), nullable=True),
        sa.Column("offices", postgresql.JSONB(), nullable=True),
        sa.Column("agency", sa.String(50), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── enforcement_records ────────────────────────────────────────────────────
    op.create_table(
        "enforcement_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agency", sa.String(50), nullable=False),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("issue_date", sa.String(20), nullable=True),
        sa.Column("company_cited", sa.String(255), nullable=True),
        sa.Column("sub_sectors", postgresql.JSONB(), nullable=True),
        sa.Column("observation_categories", postgresql.JSONB(), nullable=True),
        sa.Column("cfr_citations", postgresql.JSONB(), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("observations", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.String(100), nullable=True),
        sa.Column("pattern_tags", postgresql.JSONB(), nullable=True),
        sa.Column("severity_indicator", sa.String(20), nullable=True),
        sa.Column("trending", sa.Boolean(), nullable=True),
        sa.Column("trend_velocity", sa.Float(), nullable=True),
        sa.Column("embedding", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enforcement_records_agency", "enforcement_records", ["agency"])
    op.create_index("ix_enforcement_records_reference", "enforcement_records", ["reference_number"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("resource_label", sa.String(500), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_company_id", "audit_logs", ["company_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])

    # ── readiness_scores ───────────────────────────────────────────────────────
    op.create_table(
        "readiness_scores",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("scope_identifier", sa.String(100), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_band", sa.String(20), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("component_scores", postgresql.JSONB(), nullable=True),
        sa.Column("gap_count", sa.Integer(), nullable=True),
        sa.Column("missing_documents", sa.Integer(), nullable=True),
        sa.Column("expired_documents", sa.Integer(), nullable=True),
        sa.Column("previous_score", sa.Float(), nullable=True),
        sa.Column("trend_direction", sa.String(10), nullable=True),
        sa.Column("trend_magnitude", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── inspections ────────────────────────────────────────────────────────────
    op.create_table(
        "inspections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("agency", sa.String(50), nullable=True),
        sa.Column("inspection_type", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("day_count", sa.Integer(), nullable=True),
        sa.Column("team_assignments", postgresql.JSONB(), nullable=True),
        sa.Column("ai_agents_active", postgresql.JSONB(), nullable=True),
        sa.Column("total_requests", sa.Integer(), nullable=True),
        sa.Column("commitments_made", postgresql.JSONB(), nullable=True),
        sa.Column("observations_noted", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )

    # ── inspection_requests ────────────────────────────────────────────────────
    op.create_table(
        "inspection_requests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("inspection_id", sa.String(), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("criticality", sa.String(20), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("assigned_to", sa.String(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_time_minutes", sa.Integer(), nullable=True),
        sa.Column("ai_suggested_documents", postgresql.JSONB(), nullable=True),
        sa.Column("ai_talking_points", postgresql.JSONB(), nullable=True),
        sa.Column("ai_risk_assessment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"]),
    )

    # ── inspection_log ─────────────────────────────────────────────────────────
    op.create_table(
        "inspection_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("inspection_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("timestamp_local", sa.String(30), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("participants", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["inspection_id"], ["inspections.id"]),
    )


def downgrade() -> None:
    op.drop_table("inspection_log")
    op.drop_table("inspection_requests")
    op.drop_table("inspections")
    op.drop_table("readiness_scores")
    op.drop_table("audit_logs")
    op.drop_table("enforcement_records")
    op.drop_table("failure_modes")
    op.drop_table("regulatory_corpus")
    op.drop_table("findings")
    op.drop_table("assessments")
    op.drop_table("document_references")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("companies")
