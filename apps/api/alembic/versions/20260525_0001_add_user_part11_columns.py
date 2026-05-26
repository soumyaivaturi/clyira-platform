"""Add missing Part 11 security columns to users table

Revision ID: 20260525_0001
Revises: 001_baseline
Create Date: 2026-05-25

Adds columns that exist in the User model but were missing from the baseline
migration, causing 500 errors on every login attempt:
  - failed_login_attempts  (§11.300 lockout counter)
  - locked_until           (lockout expiry timestamp)
  - force_password_change  (admin-forced reset flag)
  - terms_accepted_at      (§11.10(j) policy acknowledgment)
  - password_changed_at    (last password change timestamp)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260525_0001"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use ADD COLUMN IF NOT EXISTS so this is safe to run on a DB that already
    # has these columns (e.g., if the migration is re-stamped and re-run).
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITHOUT TIME ZONE"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN NOT NULL DEFAULT FALSE"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP WITHOUT TIME ZONE"))
    op.execute(sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITHOUT TIME ZONE"))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "force_password_change")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
