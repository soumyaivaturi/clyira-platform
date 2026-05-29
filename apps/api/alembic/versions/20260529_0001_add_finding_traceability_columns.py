"""add engine traceability columns to findings

Revision ID: 20260529_0001
Revises: 20260528_0001
Create Date: 2026-05-29

These columns were accidentally placed on finding_comments instead of findings.
They are needed by _store_findings in assessment_service.py.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260529_0001"
down_revision = "20260528_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        ALTER TABLE findings
            ADD COLUMN IF NOT EXISTS verification_state   VARCHAR(10),
            ADD COLUMN IF NOT EXISTS field_criticality    VARCHAR(10),
            ADD COLUMN IF NOT EXISTS source_page          INTEGER,
            ADD COLUMN IF NOT EXISTS human_verification_required BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS extraction_confidence FLOAT,
            ADD COLUMN IF NOT EXISTS explanation_trace    JSONB
    """))
    # Also add to finding_comments where the model already defines them
    op.execute(sa.text("""
        ALTER TABLE finding_comments
            ADD COLUMN IF NOT EXISTS verification_state   VARCHAR(10),
            ADD COLUMN IF NOT EXISTS field_criticality    VARCHAR(10),
            ADD COLUMN IF NOT EXISTS source_page          INTEGER,
            ADD COLUMN IF NOT EXISTS human_verification_required BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS extraction_confidence FLOAT,
            ADD COLUMN IF NOT EXISTS explanation_trace    JSONB
    """))


def downgrade():
    for col in ("verification_state", "field_criticality", "source_page",
                "human_verification_required", "extraction_confidence", "explanation_trace"):
        op.execute(sa.text(f"ALTER TABLE findings DROP COLUMN IF EXISTS {col}"))
        op.execute(sa.text(f"ALTER TABLE finding_comments DROP COLUMN IF EXISTS {col}"))
