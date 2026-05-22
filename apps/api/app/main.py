"""
Clyira API — Main Application Entry Point
Quality Intelligence Platform for Life Sciences
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.routers import auth, documents, assessments, companies, readiness, inspections


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events"""
    # Auto-create all DB tables from SQLAlchemy models (safe to run repeatedly)
    import asyncio
    from sqlalchemy import text
    from app.models import Base
    from app.core.database import engine
    for attempt in range(5):
        try:
            # Extensions in isolated transactions — failures are non-fatal
            for ext in ("uuid-ossp", "vector"):
                try:
                    async with engine.begin() as conn:
                        await conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
                except Exception:
                    pass
            # Create all tables
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Add any columns missing from existing tables (schema drift fix)
            async with engine.begin() as conn:
                for table in Base.metadata.sorted_tables:
                    result = await conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=:t"
                    ), {"t": table.name})
                    existing = {row[0] for row in result}
                    for col in table.columns:
                        if col.name not in existing:
                            col_type = col.type.compile(engine.dialect)
                            await conn.execute(text(
                                f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS "{col.name}" {col_type}'
                            ))
                            print(f"  Migration   : added {table.name}.{col.name} ({col_type})")

            print("  Database    : connected and schema ready")
            break
        except Exception as e:
            print(f"  Database    : connection attempt {attempt + 1}/5 failed — {e}")
            if attempt == 4:
                print("  Database    : could not connect after 5 attempts, continuing anyway")
            else:
                await asyncio.sleep(3)

    from app.dtap import DTAPRegistry
    DTAPRegistry.initialize()

    has_key = bool(settings.GEMINI_API_KEY)
    print(f"Clyira API v{settings.APP_VERSION} starting...")
    print(f"  Environment : {settings.ENVIRONMENT}")
    print(f"  Gemini Model: {settings.GEMINI_MODEL}")
    print(f"  LLM Engine  : {'enabled' if has_key else 'DISABLED (no API key)'}")
    print(f"  DTAP Profiles: {len(DTAPRegistry.list_all())} loaded")
    yield
    print("Clyira API shutting down...")


app = FastAPI(
    title="Clyira API",
    description="Quality Intelligence Platform for Life Sciences — Document Assessment, Audit Readiness, and Real-Time Audit Support",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    redirect_slashes=False,  # prevents 307 redirects that strip Auth headers through Vercel proxy
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Config diagnostics — shows which keys are present (never reveals values)
@app.get("/debug/config")
async def debug_config():
    import os
    return {
        "GEMINI_API_KEY": "set" if settings.GEMINI_API_KEY else "MISSING",
        "GEMINI_MODEL": settings.GEMINI_MODEL,
        "DATABASE_URL": "set" if settings.DATABASE_URL else "MISSING",
        "ENVIRONMENT": settings.ENVIRONMENT,
    }


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": "clyira-api",
    }


# DB diagnostics — shows tables, columns, and row counts
@app.get("/debug/tables")
async def debug_tables():
    from sqlalchemy import text
    from app.core.database import engine
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' ORDER BY table_name, ordinal_position"
            ))
            schema: dict = {}
            for table_name, col_name in result:
                schema.setdefault(table_name, []).append(col_name)

            # Row counts for key tables
            counts: dict = {}
            for table in schema:
                try:
                    r = await conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                    counts[table] = r.scalar()
                except Exception:
                    counts[table] = "?"

        return {"status": "connected", "tables": schema, "row_counts": counts, "count": len(schema)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# API info
@app.get("/")
async def root():
    return {
        "name": "Clyira API",
        "version": settings.APP_VERSION,
        "description": "Quality Intelligence Platform for Life Sciences",
        "modules": {
            "document_creator": "AI-powered document creation and assessment",
            "audit_readiness": "Continuous readiness scoring and mock inspections",
            "audit_support": "Real-time inspection support with AI agents",
        },
    }


# Register routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(companies.router, prefix="/api/v1/companies", tags=["Companies"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["Assessments"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["Audit Readiness"])
app.include_router(inspections.router, prefix="/api/v1/inspections", tags=["Real-Time Audit Support"])


# Admin: seed enforcement corpus via HTTP (protected by secret header)
@app.post("/admin/seed-enforcement")
async def seed_enforcement_corpus(
    request: Request,
    years: int = 3,
    source: str = "all",
):
    import os, asyncio
    from fastapi import Request
    import os as _os, asyncio as _asyncio
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != _os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=403, detail="Forbidden")

    async def _run_seed():
        import sys
        sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "scripts"))
        import httpx as _httpx
        from seed_enforcement import (
            fetch_openfda, fetch_warning_letters, fetch_ema_noncompliance,
            parse_openfda_record, compute_trends, write_to_db, OPENFDA_ENDPOINTS,
        )
        from app.core.database import engine as _engine
        db_url = str(_engine.url)
        records: list = []
        async with _httpx.AsyncClient(follow_redirects=True) as client:
            if source in ("all", "fda"):
                for ep_key in ("drug_enforcement", "device_enforcement"):
                    raw = await fetch_openfda(client, OPENFDA_ENDPOINTS[ep_key], years)
                    records.extend(parse_openfda_record(r, ep_key.split("_")[0]) for r in raw)
            if source in ("all", "wl"):
                records.extend(await fetch_warning_letters(client, years))
            if source in ("all", "ema"):
                records.extend(await fetch_ema_noncompliance(client, years))
        records = compute_trends(records)
        inserted = await write_to_db(records, db_url)
        print(f"Enforcement seeder done: {inserted} new records")

    _asyncio.create_task(_run_seed())
    return {"status": "seeding_started", "source": source, "years": years}
