"""
CDMO Sponsor Programs — Multi-sponsor tenancy for CDMO accounts.
Each sponsor has its own DTAP overlay, CPP/IPC ranges, and evidence template.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.sponsor_program import SponsorProgram
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class SponsorProgramCreate(BaseModel):
    sponsor_name: str
    sponsor_code: str
    dtap_overlay: Optional[dict] = None
    cpp_ipc_ranges: Optional[dict] = None
    quality_agreement_reference: Optional[str] = None
    evidence_template_id: Optional[str] = None


class SponsorProgramUpdate(BaseModel):
    sponsor_name: Optional[str] = None
    sponsor_code: Optional[str] = None
    dtap_overlay: Optional[dict] = None
    cpp_ipc_ranges: Optional[dict] = None
    quality_agreement_reference: Optional[str] = None
    evidence_template_id: Optional[str] = None
    active: Optional[bool] = None


def _sponsor_out(sp: SponsorProgram) -> dict:
    return {
        "id": sp.id,
        "company_id": sp.company_id,
        "sponsor_name": sp.sponsor_name,
        "sponsor_code": sp.sponsor_code,
        "dtap_overlay": sp.dtap_overlay,
        "cpp_ipc_ranges": sp.cpp_ipc_ranges,
        "quality_agreement_reference": sp.quality_agreement_reference,
        "evidence_template_id": sp.evidence_template_id,
        "active": sp.active,
        "created_at": str(sp.created_at),
        "updated_at": str(sp.updated_at),
    }


@router.get("")
async def list_sponsor_programs(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sponsor programs for this company."""
    q = select(SponsorProgram).where(SponsorProgram.company_id == current_user.company_id)
    if active_only:
        q = q.where(SponsorProgram.active == True)  # noqa: E712
    q = q.order_by(SponsorProgram.sponsor_name)
    result = await db.execute(q)
    programs = result.scalars().all()
    return [_sponsor_out(sp) for sp in programs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sponsor_program(
    body: SponsorProgramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new sponsor program for CDMO multi-sponsor tenancy."""
    existing = await db.execute(
        select(SponsorProgram)
        .where(SponsorProgram.company_id == current_user.company_id)
        .where(SponsorProgram.sponsor_code == body.sponsor_code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Sponsor code '{body.sponsor_code}' already exists")

    sp = SponsorProgram(
        company_id=current_user.company_id,
        sponsor_name=body.sponsor_name,
        sponsor_code=body.sponsor_code,
        dtap_overlay=body.dtap_overlay,
        cpp_ipc_ranges=body.cpp_ipc_ranges,
        quality_agreement_reference=body.quality_agreement_reference,
        evidence_template_id=body.evidence_template_id,
        active=True,
    )
    db.add(sp)
    await db.commit()
    await db.refresh(sp)
    return _sponsor_out(sp)


@router.get("/{program_id}")
async def get_sponsor_program(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a sponsor program by ID."""
    sp = await db.get(SponsorProgram, program_id)
    if not sp or sp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Sponsor program not found")
    return _sponsor_out(sp)


@router.patch("/{program_id}")
async def update_sponsor_program(
    program_id: str,
    body: SponsorProgramUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update sponsor program fields."""
    sp = await db.get(SponsorProgram, program_id)
    if not sp or sp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Sponsor program not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sp, field, value)

    await db.commit()
    await db.refresh(sp)
    return _sponsor_out(sp)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sponsor_program(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate (soft-delete) a sponsor program."""
    sp = await db.get(SponsorProgram, program_id)
    if not sp or sp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Sponsor program not found")

    # If dossiers are linked, soft-deactivate to preserve referential integrity
    from app.models.batch_dossier import BatchDossier
    linked = await db.execute(
        select(BatchDossier).where(BatchDossier.sponsor_program_id == program_id).limit(1)
    )
    if linked.scalar_one_or_none():
        sp.active = False
        await db.commit()
        return

    await db.delete(sp)
    await db.commit()


@router.get("/{program_id}/dossiers")
async def list_sponsor_dossiers(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all batch dossiers linked to this sponsor program."""
    sp = await db.get(SponsorProgram, program_id)
    if not sp or sp.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Sponsor program not found")

    from app.models.batch_dossier import BatchDossier
    result = await db.execute(
        select(BatchDossier)
        .where(BatchDossier.sponsor_program_id == program_id)
        .order_by(BatchDossier.created_at.desc())
    )
    dossiers = result.scalars().all()
    return {
        "sponsor_program_id": program_id,
        "sponsor_name": sp.sponsor_name,
        "dossier_count": len(dossiers),
        "dossiers": [
            {
                "id": d.id,
                "lot_number": d.lot_number,
                "product_name": d.product_name,
                "status": d.status,
                "readiness_status": d.readiness_status,
                "created_at": str(d.created_at),
            }
            for d in dossiers
        ],
    }
