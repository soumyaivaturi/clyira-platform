"""add finding_comments table

Revision ID: 20260528_0001
Revises: 20260527_0003
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260528_0001"
down_revision = "20260527_0003"
branch_labels = None
depends_on = None


def upgrade():
    # IF NOT EXISTS — safe when create_all() in main.py pre-creates the table before this runs
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS finding_comments (
            id           VARCHAR NOT NULL PRIMARY KEY,
            finding_id   VARCHAR NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
            assessment_id VARCHAR NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
            user_id      VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            user_name    VARCHAR(200),
            user_role    VARCHAR(50),
            text         TEXT NOT NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_finding_comments_finding_id ON finding_comments(finding_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_finding_comments_assessment_id ON finding_comments(assessment_id)"
    ))


def downgrade():
    op.execute(sa.text("DROP INDEX IF EXISTS ix_finding_comments_assessment_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_finding_comments_finding_id"))
    op.execute(sa.text("DROP TABLE IF EXISTS finding_comments"))
