#!/bin/sh
set -e

# Bootstrap alembic version tracking for DBs created via SQLAlchemy create_all().
# If alembic_version doesn't exist yet, stamp the baseline so that the existing
# tables aren't re-created, then upgrade applies only incremental migrations.
python3 - <<'PYEOF'
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def bootstrap():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT to_regclass('public.alembic_version')"))
        if r.scalar() is None:
            await conn.execute(text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(32) NOT NULL, "
                "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            ))
            await conn.execute(text(
                "INSERT INTO alembic_version (version_num) VALUES ('001_baseline')"
            ))
            print("Stamped baseline revision — DB was bootstrapped without alembic")
        else:
            print("alembic_version exists, skipping stamp")
    await engine.dispose()

asyncio.run(bootstrap())
PYEOF

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
