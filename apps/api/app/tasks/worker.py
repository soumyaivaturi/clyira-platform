"""
Celery Worker — Async assessment jobs and background tasks.
Uses asyncio.run() to bridge sync Celery with async SQLAlchemy services.
"""
import asyncio
import logging

from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

worker = Celery(
    "clyira",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

worker.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.ASSESSMENT_TIMEOUT_SECONDS,
    worker_concurrency=settings.MAX_CONCURRENT_ASSESSMENTS,
)


async def _run_assessment_async(document_id: str, company_id: str, user_id: str) -> dict:
    """Run assessment using AsyncSession — called via asyncio.run()."""
    from app.core.database import AsyncSessionLocal
    from app.dtap import DTAPRegistry
    from app.services.assessment_service import AssessmentService

    DTAPRegistry.initialize()

    async with AsyncSessionLocal() as db:
        svc = AssessmentService(db)
        assessment = await svc.trigger_assessment(
            document_id=document_id,
            company_id=company_id,
            user_id=user_id,
            include_references=True,
        )
        return {
            "status": "completed",
            "assessment_id": assessment.id,
            "score": assessment.clyira_score,
            "score_band": assessment.score_band,
        }


@worker.task(name="run_document_assessment", bind=True, max_retries=2)
def run_document_assessment(self, document_id: str, company_id: str, user_id: str):
    """Async assessment pipeline via Celery."""
    try:
        return asyncio.run(_run_assessment_async(document_id, company_id, user_id))
    except Exception as exc:
        logger.error(f"Assessment task failed for {document_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


async def _calculate_readiness_async(company_id: str) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.readiness_service import ReadinessService

    async with AsyncSessionLocal() as db:
        svc = ReadinessService(db)
        return await svc.calculate_company_readiness(company_id)


@worker.task(name="calculate_readiness_scores")
def calculate_readiness_scores(company_id: str):
    """Recalculate readiness scores for a company."""
    try:
        return asyncio.run(_calculate_readiness_async(company_id))
    except Exception as exc:
        logger.error(f"Readiness task failed for {company_id}: {exc}")
        raise


@worker.task(name="generate_document")
def generate_document(document_id: str, company_id: str, instructions: dict):
    """AI Document Creator — requires Anthropic API key."""
    logger.info(f"Document generation queued for {document_id} (requires API key)")
    return {"status": "queued", "document_id": document_id}
