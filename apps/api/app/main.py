"""
Clyira API — Main Application Entry Point
Quality Intelligence Platform for Life Sciences
"""
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.routers import auth, documents, assessments, companies, readiness, inspections
from app.routers import assistant, export, audit, notifications, api_keys, signatures, evidence
from app.routers import batch_dossiers


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

    from app.engines.llm_engine import _active_model, _llm_available
    provider = "groq" if settings.GROQ_API_KEY else ("gemini" if settings.GEMINI_API_KEY else "none")
    print(f"Clyira API v{settings.APP_VERSION} starting...")
    print(f"  Environment : {settings.ENVIRONMENT}")
    print(f"  LLM Provider: {provider.upper()} — model: {_active_model() if _llm_available() else 'N/A'}")
    print(f"  LLM Engine  : {'enabled' if _llm_available() else 'DISABLED (no API key)'}")
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
    from app.engines.llm_engine import _active_model, _llm_available
    return {
        "LLM_PROVIDER": "groq" if settings.GROQ_API_KEY else ("gemini" if settings.GEMINI_API_KEY else "NONE"),
        "LLM_MODEL": _active_model() if _llm_available() else "NONE",
        "GROQ_API_KEY": "set" if settings.GROQ_API_KEY else "not set",
        "GEMINI_API_KEY": "set" if settings.GEMINI_API_KEY else "not set",
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
app.include_router(export.router, prefix="/api/v1/assessments", tags=["Export"])
app.include_router(assistant.router, prefix="/api/v1/assistant", tags=["Author & QA Assistant"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit Trail"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["Audit Readiness"])
app.include_router(inspections.router, prefix="/api/v1/inspections", tags=["Real-Time Audit Support"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["API Keys"])
app.include_router(signatures.router, prefix="/api/v1/documents", tags=["Electronic Signatures"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence Fabric"])
app.include_router(batch_dossiers.router, prefix="/api/v1/batch-dossiers", tags=["Batch & Lot Record Review"])


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


# Debug: show last N assessments (any status) with finding counts (admin only)
@app.get("/debug/recent-assessments")
async def debug_recent_assessments(request: Request, n: int = 10):
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT id, document_id, status, clyira_score, "
            "findings_critical, findings_high, findings_medium, findings_low, findings_info, "
            "model_version, processing_time_seconds, error_detail, created_at "
            "FROM assessments ORDER BY created_at DESC LIMIT :n"
        ), {"n": n})
        rows = result.fetchall()
    return [
        {
            "id": r[0], "document_id": r[1], "status": r[2], "score": r[3],
            "findings": {"critical": r[4], "high": r[5], "medium": r[6], "low": r[7], "info": r[8]},
            "model": r[9], "processing_s": r[10],
            "error": r[11][:200] if r[11] else None,
            "created_at": str(r[12]),
        }
        for r in rows
    ]


# Debug: test Groq API directly (admin only)
@app.get("/debug/test-groq")
async def debug_test_groq(request: Request):
    import os, time
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    if not settings.GROQ_API_KEY:
        return {"status": "error", "detail": "GROQ_API_KEY not set"}
    try:
        import httpx
        t0 = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [{"role": "user", "content": "Reply with exactly: GROQ_OK"}],
                    "max_tokens": 10,
                },
            )
        elapsed = round(time.time() - t0, 2)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            usage = resp.json().get("usage", {})
            return {"status": "ok", "response": content, "elapsed_s": elapsed,
                    "model": settings.GROQ_MODEL, "usage": usage}
        else:
            return {"status": "error", "http_status": resp.status_code, "body": resp.text[:300]}
    except Exception as e:
        return {"status": "error", "detail": f"{type(e).__name__}: {e}"}


# Debug: show error detail for last N failed assessments (admin only)
@app.get("/debug/assessment-errors")
async def debug_assessment_errors(request: Request, n: int = 5):
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    from sqlalchemy import text
    from app.core.database import engine
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT id, document_id, status, error_detail, processing_time_seconds, created_at "
            "FROM assessments WHERE status='failed' ORDER BY created_at DESC LIMIT :n"
        ), {"n": n})
        rows = result.fetchall()
    return [
        {"id": r[0], "document_id": r[1], "status": r[2],
         "error": r[3], "processing_time_s": r[4], "created_at": str(r[5])}
        for r in rows
    ]


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


# Admin: seed enforcement_records from bundled observations.jsonl (no external calls)
@app.post("/admin/seed-from-corpus")
async def seed_from_corpus(request: Request, background_tasks: BackgroundTasks):
    """
    Populate enforcement_records from the bundled rag_index/observations.jsonl.
    Fast, no external HTTP — uses the 2,919 FDA Warning Letter observations
    already bundled in the Docker image.
    """
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    async def _do_seed():
        import json, re
        from pathlib import Path
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.regulatory import EnforcementRecord
        from app.models.base import generate_uuid

        JSONL_PATHS = [
            Path(__file__).parent.parent / "rag_index" / "observations.jsonl",
            Path.home() / "Documents" / "Clyira-Corpus" / "rag_index" / "observations.jsonl",
        ]
        jsonl_path = next((p for p in JSONL_PATHS if p.exists()), None)
        if not jsonl_path:
            print("seed-from-corpus: observations.jsonl not found")
            return

        CATEGORY_KW = {
            "data_integrity": ["data integrity", "alcoa", "falsif", "fabricat", "audit trail", "electronic record", "chromatogram", "raw data", "21 cfr 11"],
            "lab_data": ["out-of-specification", "oos", "oot", "laboratory", "analytical method", "method validation", "retest", "hplc", "system suitability"],
            "capa": ["corrective action", "preventive action", "capa", "investigation", "root cause", "effectiveness check"],
            "process_validation": ["process validation", "validation protocol", "cpv", "ipc", "in-process control"],
            "equipment_qualification": ["equipment qualification", "calibration", "preventive maintenance"],
            "training": ["training", "qualification of personnel", "competency", "gmp training"],
            "environmental_monitoring": ["environmental monitoring", "bioburden", "endotoxin", "microbial", "contamination"],
            "sterility_assurance": ["sterility", "aseptic", "sterilization", "media fill"],
            "documentation": ["batch record", "logbook", "record keeping", "written procedure", "sop ", "standard operating"],
            "change_control": ["change control", "change management", "post-approval change"],
            "stability": ["stability", "shelf life", "expiry", "degradation"],
        }
        CFR_PATTERN = re.compile(r'21\s+CFR\s+[\w.]+(?:\([a-z]\))?', re.IGNORECASE)

        def _cats(text: str):
            tl = text.lower()
            return [c for c, kws in CATEGORY_KW.items() if any(k in tl for k in kws)]

        def _cfr(text: str):
            return list(dict.fromkeys(CFR_PATTERN.findall(text)))

        observations = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        observations.append(json.loads(line))
                    except Exception:
                        pass

        print(f"seed-from-corpus: loaded {len(observations)} observations from {jsonl_path}")

        inserted = 0
        skipped = 0
        async with AsyncSessionLocal() as db:
            for obs in observations:
                ref = obs.get("id", "")
                if ref:
                    existing = await db.execute(
                        select(EnforcementRecord).where(EnforcementRecord.reference_number == ref)
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
                        continue

                text_body = obs.get("text", "")
                subject = obs.get("subject", "")
                company = obs.get("company", "Unknown")
                year = str(obs.get("year", ""))
                cfr_from_jsonl = obs.get("cfr_citations", [])
                cfr_extracted = _cfr(text_body)
                all_cfr = list(dict.fromkeys(cfr_from_jsonl + cfr_extracted))

                record = EnforcementRecord(
                    id=generate_uuid(),
                    agency="FDA",
                    record_type="warning_letter",
                    reference_number=ref[:100] if ref else None,
                    issue_date=f"{year}-01-01" if year.isdigit() else None,
                    company_cited=company[:255],
                    sub_sectors=[],
                    observation_categories=_cats(text_body + " " + subject),
                    cfr_citations=all_cfr[:20],
                    title=(subject or text_body[:200])[:500],
                    summary=text_body[:1000],
                    observations=[text_body[:2000]] if text_body else [],
                    outcome="warning_letter_issued",
                    pattern_tags=[],
                    severity_indicator="high",
                    trending=False,
                    trend_velocity=None,
                )
                db.add(record)
                inserted += 1

                if inserted % 200 == 0:
                    await db.commit()
                    print(f"seed-from-corpus: committed {inserted} records…")

            await db.commit()

        print(f"seed-from-corpus: done — inserted={inserted}, skipped={skipped}")

    background_tasks.add_task(_do_seed)
    return {"status": "seeding_started", "source": "observations.jsonl", "message": "Check server logs for progress."}


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


# Admin: seed regulatory_corpus from bundled regulatory_corpus.jsonl
@app.post("/admin/seed-regulatory-corpus")
async def seed_regulatory_corpus(request: Request, background_tasks: BackgroundTasks):
    """
    Populate regulatory_corpus table from the bundled rag_index/regulatory_corpus.jsonl.
    Contains 21 CFR Parts 11, 58, 210, 211, 212, 600, 606, 610, 820 — section-level text.
    Idempotent: skips records whose citation_reference already exists.
    """
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    async def _do_seed():
        import json
        from pathlib import Path
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.regulatory import RegulatoryCorpus
        from app.models.base import generate_uuid

        JSONL_PATHS = [
            Path(__file__).parent.parent / "rag_index" / "regulatory_corpus.jsonl",
            Path.home() / "Documents" / "Clyira-Corpus" / "rag_index" / "regulatory_corpus.jsonl",
        ]
        jsonl_path = next((p for p in JSONL_PATHS if p.exists()), None)
        if not jsonl_path:
            print("seed-regulatory-corpus: regulatory_corpus.jsonl not found")
            return

        records = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass

        print(f"seed-regulatory-corpus: loaded {len(records)} sections from {jsonl_path}")

        inserted = 0
        skipped = 0
        async with AsyncSessionLocal() as db:
            for r in records:
                citation = r.get("citation_reference", "")
                if citation:
                    existing = await db.execute(
                        select(RegulatoryCorpus).where(
                            RegulatoryCorpus.citation_reference == citation
                        )
                    )
                    if existing.scalar_one_or_none():
                        skipped += 1
                        continue

                row = RegulatoryCorpus(
                    id=generate_uuid(),
                    hierarchy_level=r.get("hierarchy_level", 2),
                    agency=r.get("agency", "FDA"),
                    document_type=r.get("document_type", "regulation"),
                    title=r.get("title", "")[:500],
                    citation_reference=citation[:200] if citation else None,
                    section=r.get("section", "")[:200],
                    content=r.get("content", ""),
                    effective_date=r.get("effective_date"),
                    sub_sectors=r.get("sub_sectors", []),
                    document_categories=r.get("document_categories", []),
                    departments=[],
                    is_current=r.get("is_current", True),
                )
                db.add(row)
                inserted += 1

                if inserted % 50 == 0:
                    await db.commit()
                    print(f"seed-regulatory-corpus: committed {inserted} records…")

            await db.commit()

        print(f"seed-regulatory-corpus: done — inserted={inserted}, skipped={skipped}")

    background_tasks.add_task(_do_seed)
    return {
        "status": "seeding_started",
        "source": "regulatory_corpus.jsonl",
        "message": "Check server logs for progress.",
    }


# Admin: seed failure_modes from bundled failure_modes.jsonl
@app.post("/admin/seed-failure-modes")
async def seed_failure_modes(request: Request, background_tasks: BackgroundTasks):
    """
    Populate failure_modes table from the bundled rag_index/failure_modes.jsonl.
    Contains 20 named failure patterns clustered from 2,919 FDA enforcement observations.
    Idempotent: upserts by id (FM-001, FM-002, …).
    """
    import os
    secret = request.headers.get("X-Admin-Secret", "")
    if secret != os.environ.get("ADMIN_SECRET", "clyira-admin-secret"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")

    async def _do_seed():
        import json
        from pathlib import Path
        from app.core.database import AsyncSessionLocal
        from app.models.regulatory import FailureMode

        JSONL_PATHS = [
            Path(__file__).parent.parent / "rag_index" / "failure_modes.jsonl",
        ]
        jsonl_path = next((p for p in JSONL_PATHS if p.exists()), None)
        if not jsonl_path:
            print("seed-failure-modes: failure_modes.jsonl not found")
            return

        records = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass

        print(f"seed-failure-modes: loaded {len(records)} failure modes from {jsonl_path}")

        inserted = 0
        updated = 0
        async with AsyncSessionLocal() as db:
            for r in records:
                existing = await db.get(FailureMode, r["id"])
                if existing:
                    # Update in-place (frequency may change as corpus grows)
                    existing.name = r["name"]
                    existing.description = r["description"]
                    existing.frequency = r.get("frequency", 0)
                    existing.affected_companies_count = r.get("affected_companies_count", 0)
                    existing.primary_cfr_citations = r.get("primary_cfr_citations", [])
                    existing.observed_cfr_sections = r.get("observed_cfr_sections", [])
                    existing.keywords = r.get("keywords", [])
                    existing.severity_range = r.get("severity_range", [])
                    existing.doc_categories = r.get("doc_categories", [])
                    existing.sub_sectors = r.get("sub_sectors", [])
                    existing.root_cause_categories = r.get("root_cause_categories", [])
                    existing.evidence_indicators = r.get("evidence_indicators", [])
                    existing.example_observation_ids = r.get("example_observation_ids", [])
                    existing.observation_years = r.get("observation_years", [])
                    existing.offices = r.get("offices", {})
                    updated += 1
                else:
                    fm = FailureMode(
                        id=r["id"],
                        name=r["name"],
                        description=r["description"],
                        frequency=r.get("frequency", 0),
                        affected_companies_count=r.get("affected_companies_count", 0),
                        primary_cfr_citations=r.get("primary_cfr_citations", []),
                        observed_cfr_sections=r.get("observed_cfr_sections", []),
                        keywords=r.get("keywords", []),
                        severity_range=r.get("severity_range", []),
                        doc_categories=r.get("doc_categories", []),
                        sub_sectors=r.get("sub_sectors", []),
                        root_cause_categories=r.get("root_cause_categories", []),
                        evidence_indicators=r.get("evidence_indicators", []),
                        example_observation_ids=r.get("example_observation_ids", []),
                        observation_years=r.get("observation_years", []),
                        offices=r.get("offices", {}),
                        agency=r.get("agency", "FDA"),
                        is_current=r.get("is_current", True),
                    )
                    db.add(fm)
                    inserted += 1

            await db.commit()

        print(f"seed-failure-modes: done — inserted={inserted}, updated={updated}")

    background_tasks.add_task(_do_seed)
    return {
        "status": "seeding_started",
        "source": "failure_modes.jsonl",
        "failure_modes_count": 20,
        "message": "Check server logs for progress.",
    }
