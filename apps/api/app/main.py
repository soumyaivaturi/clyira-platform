"""
Clyira API — Main Application Entry Point
Quality Intelligence Platform for Life Sciences
"""
from fastapi import BackgroundTasks, FastAPI, Request
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


@app.get("/debug/llm")
async def debug_llm():
    """List available Gemini models for this API key, then test the first usable one"""
    if not settings.GEMINI_API_KEY:
        return {"status": "error", "detail": "GEMINI_API_KEY not set"}
    try:
        import httpx, time
        async with httpx.AsyncClient(timeout=30.0) as client:
            # List models on both v1 and v1beta
            results = {}
            for api_ver in ("v1", "v1beta"):
                r = await client.get(
                    f"https://generativelanguage.googleapis.com/{api_ver}/models",
                    params={"key": settings.GEMINI_API_KEY},
                )
                if r.status_code == 200:
                    models = r.json().get("models", [])
                    results[api_ver] = [
                        m["name"] for m in models
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                else:
                    results[api_ver] = f"error {r.status_code}: {r.text[:100]}"

            # Try to call the first available generateContent model
            test_result = {}
            candidates = results.get("v1beta", []) if isinstance(results.get("v1beta"), list) else []
            if candidates:
                model_name = candidates[0].replace("models/", "")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                t0 = time.time()
                r = await client.post(
                    url,
                    params={"key": settings.GEMINI_API_KEY},
                    json={"contents": [{"role": "user", "parts": [{"text": "Say OK"}]}],
                          "generationConfig": {"maxOutputTokens": 5}},
                )
                elapsed = round(time.time() - t0, 2)
                if r.status_code == 200:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                    test_result = {"model_tested": model_name, "ok": True, "elapsed_s": elapsed, "response": text}
                else:
                    test_result = {"model_tested": model_name, "ok": False, "error": r.text[:200]}

        return {"available_models": results, "test": test_result}
    except Exception as e:
        return {"status": "error", "detail": f"{type(e).__name__}: {e}"}


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


@app.get("/debug/doc-text/{document_id}")
async def debug_doc_text(document_id: str, request: Request):
    """Show extracted_text length and preview for a document (admin only)"""
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT id, title, file_type, status, length(extracted_text) as text_len, left(extracted_text, 500) as preview FROM documents WHERE id=:id"),
            {"id": document_id}
        )
        row = r.fetchone()
        if not row:
            return {"error": "not found"}
        return {"id": row[0], "title": row[1], "file_type": row[2], "status": row[3], "text_length": row[4], "preview": row[5]}


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


async def _run_enforcement_seed(source: str, years: int) -> None:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import httpx
    from seed_enforcement import (
        fetch_openfda, fetch_warning_letters, fetch_ema_noncompliance,
        parse_openfda_record, compute_trends, write_to_db, OPENFDA_ENDPOINTS,
    )
    from app.core.database import engine as _engine
    # render_as_string preserves the password (str() obscures it with ***)
    db_url = _engine.url.render_as_string(hide_password=False)
    records: list = []
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "Clyira/1.0 (enforcement corpus builder)"},
            timeout=60.0,
        ) as client:
            if source in ("all", "fda"):
                for ep_key in ("drug_enforcement", "device_enforcement"):
                    raw = await fetch_openfda(client, OPENFDA_ENDPOINTS[ep_key], years)
                    records.extend(parse_openfda_record(r, ep_key.split("_")[0]) for r in raw)
                    print(f"  openFDA {ep_key}: {len(raw)} raw records")
            if source in ("all", "wl"):
                wl = await fetch_warning_letters(client, years)
                records.extend(wl)
                print(f"  Warning letters: {len(wl)} records")
            if source in ("all", "ema"):
                ema = await fetch_ema_noncompliance(client, years)
                records.extend(ema)
                print(f"  EMA non-compliance: {len(ema)} records")
        records = compute_trends(records)
        inserted = await write_to_db(records, db_url)
        print(f"Enforcement seeder complete: {inserted} new records inserted (total fetched={len(records)})")
    except Exception as e:
        print(f"Enforcement seeder ERROR: {e}")
        raise


# Admin: reset stuck assessments (status=running → failed)
@app.post("/admin/reset-stuck-assessments")
async def reset_stuck_assessments(request: Request):
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    from sqlalchemy import text
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            "UPDATE assessments SET status='failed' WHERE status='running' "
            "RETURNING id, document_id"
        ))
        rows = result.fetchall()
        await db.commit()
    return {"reset": len(rows), "ids": [str(r[0]) for r in rows]}


# Admin: seed enforcement corpus via HTTP (protected by secret header)
@app.post("/admin/seed-enforcement")
async def seed_enforcement_corpus(
    request: Request,
    background_tasks: BackgroundTasks,
    years: int = 3,
    source: str = "all",
):
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(_run_enforcement_seed, source, years)
    return {"status": "seeding_started", "source": source, "years": years}


# Debug: test seeder connectivity + first-pass synchronously (admin only)
@app.get("/debug/seed-test")
async def debug_seed_test(request: Request):
    import os, sys, traceback
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        import httpx
        from app.core.database import engine as _engine
        db_url = _engine.url.render_as_string(hide_password=False)
        # Direct test — no seed_enforcement import, just raw httpx
        cutoff = "20240101"
        params = {"search": f"report_date:[{cutoff} TO 99991231]", "limit": 3}
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get("https://api.fda.gov/drug/enforcement.json", params=params)
        actual_url = str(resp.url)
        data = resp.json()
        results = data.get("results", [])
        return {
            "http_status": resp.status_code,
            "actual_url": actual_url,
            "total_available": data.get("meta", {}).get("results", {}).get("total"),
            "raw_count": len(results),
            "first_firm": results[0].get("recalling_firm", "") if results else None,
            "db_url_prefix": db_url[:40] + "***",
        }
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()[-500:]}


# Admin: re-extract document text for documents with empty extracted_text
@app.post("/admin/reextract-documents")
async def reextract_documents(request: Request):
    """Re-extract text for all documents with empty extracted_text (e.g. DOCX table content bug)."""
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    from sqlalchemy import text, select
    from app.core.database import AsyncSessionLocal
    from app.models.document import Document
    from app.services.document_service import DocumentService

    updated = []
    skipped = []
    errors = []

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Document).where(
                (Document.extracted_text == None) | (Document.extracted_text == "")
            )
        )
        docs = result.scalars().all()

        svc = DocumentService(db)

        for doc in docs:
            try:
                # Try to fetch file content from storage
                content = None
                if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY and doc.file_path:
                    try:
                        from supabase import create_client
                        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
                        content = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(doc.file_path)
                    except Exception as e:
                        errors.append({"id": doc.id, "title": doc.title, "error": f"Storage download: {e}"})
                        continue
                elif doc.file_path and os.path.exists(doc.file_path):
                    with open(doc.file_path, "rb") as f:
                        content = f.read()

                if not content:
                    skipped.append({"id": doc.id, "title": doc.title, "reason": "file not accessible"})
                    continue

                file_type = doc.file_type or "unknown"
                new_text = await svc._extract_text_from_bytes(content, file_type)
                if not new_text:
                    skipped.append({"id": doc.id, "title": doc.title, "reason": "extraction returned empty"})
                    continue

                doc.extracted_text = new_text
                doc.extracted_sections = svc._identify_sections(new_text)
                await db.commit()
                updated.append({"id": doc.id, "title": doc.title, "chars": len(new_text)})

            except Exception as e:
                errors.append({"id": doc.id, "title": doc.title, "error": str(e)})

    return {
        "status": "done",
        "updated": len(updated),
        "skipped": len(skipped),
        "errors": len(errors),
        "details": {"updated": updated, "skipped": skipped, "errors": errors},
    }
