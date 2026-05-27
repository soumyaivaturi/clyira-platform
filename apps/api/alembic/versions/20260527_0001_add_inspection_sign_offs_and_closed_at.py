"""Add sign_offs and closed_at columns to inspections table

Revision ID: 20260527_0001
Revises: 20260525_0001
Create Date: 2026-05-27

sign_offs: JSONB object tracking management approval sign-offs for the
  post-inspection 483 response workflow (qa_lead, site_director, reg_affairs, legal).
  Persisted so page refresh doesn't lose legally-significant approval state.

closed_at: ISO timestamp set when the inspection transitions to post_inspection.
  Used as the base date for the 15-business-day FDA 483 response deadline.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0001"
down_revision: Union[str, None] = "20260525_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS sign_offs JSONB DEFAULT '{}'::jsonb"
    ))
    op.execute(sa.text(
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS closed_at VARCHAR(50)"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE inspections DROP COLUMN IF EXISTS sign_offs"))
    op.execute(sa.text("ALTER TABLE inspections DROP COLUMN IF EXISTS closed_at"))
