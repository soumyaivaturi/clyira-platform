#!/bin/sh
set -e

# Apply schema migrations directly — avoids alembic bootstrapping complexity
# on DBs that were created via SQLAlchemy create_all() with no alembic history.
# All statements use IF NOT EXISTS / IF EXISTS so this is fully idempotent.
python3 - <<'PYEOF'
import asyncio, os, sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

raw_url = os.environ.get("DATABASE_URL", "")
if not raw_url:
    print("ERROR: DATABASE_URL not set", file=sys.stderr)
    sys.exit(1)

# Ensure asyncpg driver scheme for SQLAlchemy async
url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

MIGRATIONS = [
    # users — Part 11 security columns missing from baseline
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP WITHOUT TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP WITHOUT TIME ZONE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP WITHOUT TIME ZONE",
    # audit_logs — columns missing from baseline (cause login 500 via aborted transaction)
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS action VARCHAR(20)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS before_state JSONB",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS after_state JSONB",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR(64)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entry_hash VARCHAR(64)",
]

async def main():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        for stmt in MIGRATIONS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("Schema migration complete")

asyncio.run(main())
PYEOF

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
