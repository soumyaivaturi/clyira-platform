"""
Clyira API — Main Application Entry Point
Quality Intelligence Platform for Life Sciences
"""
from fastapi import FastAPI
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
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "service": "clyira-api",
    }


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
