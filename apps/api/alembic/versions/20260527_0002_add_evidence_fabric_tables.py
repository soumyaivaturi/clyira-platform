"""Add Evidence Fabric tables (evidence_imports, evidence_objects)

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27

evidence_imports — one row per uploaded CSV/Excel file. Stores the full
  parsed row set (raw_rows JSONB) so column mapping can re-ingest the
  complete dataset without requiring a second upload.

evidence_objects — normalized evidence records created when the user
  confirms column mapping. One row per CSV/Excel row after normalization.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260527_0002"
down_revision: Union[str, None] = "20260527_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS evidence_imports (
            id              VARCHAR PRIMARY KEY,
            company_id      VARCHAR NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            uploaded_by     VARCHAR REFERENCES users(id) ON DELETE SET NULL,
            filename        VARCHAR(500) NOT NULL,
            source_system   VARCHAR(100),
            record_count    INTEGER DEFAULT 0,
            status          VARCHAR(30) DEFAULT 'processing',
            error_message   TEXT,
            detected_columns JSONB DEFAULT '[]'::jsonb,
            column_mapping   JSONB DEFAULT '{}'::jsonb,
            entity_type      VARCHAR(50),
            file_path        VARCHAR(500),
            raw_rows         JSONB DEFAULT '[]'::jsonb,
            created_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_imports_company_id ON evidence_imports(company_id)"
    ))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS evidence_objects (
            id                  VARCHAR PRIMARY KEY,
            import_id           VARCHAR NOT NULL REFERENCES evidence_imports(id) ON DELETE CASCADE,
            company_id          VARCHAR NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            entity_type         VARCHAR(50),
            entity_id           VARCHAR(255),
            entity_name         VARCHAR(500),
            signal_type         VARCHAR(50),
            event_date          VARCHAR(30),
            severity            VARCHAR(20),
            raw_row             JSONB DEFAULT '{}'::jsonb,
            normalized          JSONB DEFAULT '{}'::jsonb,
            linked_document_id  VARCHAR REFERENCES documents(id) ON DELETE SET NULL,
            cfr_citations       JSONB DEFAULT '[]'::jsonb,
            tags                JSONB DEFAULT '[]'::jsonb,
            created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_objects_import_id ON evidence_objects(import_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_objects_company_id ON evidence_objects(company_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_objects_entity_type ON evidence_objects(company_id, entity_type)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_objects_signal_type ON evidence_objects(company_id, signal_type)"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS evidence_objects"))
    op.execute(sa.text("DROP TABLE IF EXISTS evidence_imports"))
