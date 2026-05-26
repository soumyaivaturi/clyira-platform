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
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "force_password_change")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
