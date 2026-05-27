"""Add notification_config to inspections table

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27

notification_config: JSONB object holding per-event email notification
settings (recipients, subject/body templates, enabled flag).
Structure: { "events": { "<event_type>": { "enabled": bool,
  "recipients": [str], "subject": str, "body": str } } }
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0003"
down_revision: Union[str, None] = "20260527_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE inspections ADD COLUMN IF NOT EXISTS notification_config JSONB DEFAULT '{}'::jsonb"
    ))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE inspections DROP COLUMN IF EXISTS notification_config"))
