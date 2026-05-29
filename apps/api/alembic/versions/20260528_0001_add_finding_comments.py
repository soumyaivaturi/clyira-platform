"""add finding_comments table

Revision ID: 20260528_0001
Revises: 20260527_0001
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260528_0001"
down_revision = "20260527_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "finding_comments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("finding_id", sa.String(), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assessment_id", sa.String(), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_name", sa.String(200), nullable=True),
        sa.Column("user_role", sa.String(50), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_finding_comments_finding_id", "finding_comments", ["finding_id"])
    op.create_index("ix_finding_comments_assessment_id", "finding_comments", ["assessment_id"])


def downgrade():
    op.drop_index("ix_finding_comments_assessment_id", "finding_comments")
    op.drop_index("ix_finding_comments_finding_id", "finding_comments")
    op.drop_table("finding_comments")
