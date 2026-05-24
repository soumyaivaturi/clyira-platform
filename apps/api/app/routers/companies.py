"""
Company Management & Onboarding Router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.company import Company
from app.models.user import User

router = APIRouter()


class OnboardingRequest(BaseModel):
    sub_sectors: list[str]
    agencies: list[str]
    markets: list[str]
    certifications: list[str] = []


class CompanyResponse(BaseModel):
    id: str
    name: str
    slug: str
    sub_sectors: list[str]
    agencies: list[str]
    markets: list[str]
    certifications: list[str]
    onboarding_complete: bool

    class Config:
        from_attributes = True


@router.post("/onboard", response_model=CompanyResponse)
async def onboard_company(
    data: OnboardingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save company regulatory configuration after registration.
    Sets onboarding_complete = True, activating the full platform.
    """
    result = await db.execute(select(Company).where(Company.id == current_user.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if not data.sub_sectors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one sub-sector")
    if not data.agencies:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one regulatory agency")
    if not data.markets:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select at least one target market")

    company.sub_sectors = data.sub_sectors
    company.agencies = data.agencies
    company.markets = data.markets
    company.certifications = data.certifications
    company.onboarding_complete = True

    return CompanyResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        sub_sectors=company.sub_sectors,
        agencies=company.agencies,
        markets=company.markets,
        certifications=company.certifications,
        onboarding_complete=company.onboarding_complete,
    )


@router.get("/me", response_model=CompanyResponse)
async def get_my_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's company"""
    result = await db.execute(select(Company).where(Company.id == current_user.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    return CompanyResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        sub_sectors=company.sub_sectors or [],
        agencies=company.agencies or [],
        markets=company.markets or [],
        certifications=company.certifications or [],
        onboarding_complete=company.onboarding_complete,
    )


class CompanyUpdateRequest(BaseModel):
    sub_sectors: list[str] | None = None
    agencies: list[str] | None = None
    markets: list[str] | None = None
    certifications: list[str] | None = None
    name: str | None = None


@router.patch("/me", response_model=CompanyResponse)
async def update_my_company(
    data: CompanyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update mutable company profile fields (sub_sectors, agencies, markets, certifications, name)."""
    result = await db.execute(select(Company).where(Company.id == current_user.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    if data.sub_sectors is not None:
        if not data.sub_sectors:
            raise HTTPException(status_code=422, detail="At least one sub-sector is required")
        company.sub_sectors = data.sub_sectors
    if data.agencies is not None:
        if not data.agencies:
            raise HTTPException(status_code=422, detail="At least one agency is required")
        company.agencies = data.agencies
    if data.markets is not None:
        if not data.markets:
            raise HTTPException(status_code=422, detail="At least one market is required")
        company.markets = data.markets
    if data.certifications is not None:
        company.certifications = data.certifications
    if data.name is not None:
        name = data.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be empty")
        company.name = name

    await db.commit()
    await db.refresh(company)

    return CompanyResponse(
        id=company.id,
        name=company.name,
        slug=company.slug,
        sub_sectors=company.sub_sectors or [],
        agencies=company.agencies or [],
        markets=company.markets or [],
        certifications=company.certifications or [],
        onboarding_complete=company.onboarding_complete,
    )


@router.get("/{company_id}/departments")
async def get_departments(
    company_id: str,
    current_user: User = Depends(get_current_user),
):
    """Standard department taxonomy"""
    return {
        "departments": [
            {"code": "QA", "name": "Quality Assurance"},
            {"code": "QC", "name": "Quality Control"},
            {"code": "MFG", "name": "Manufacturing"},
            {"code": "VAL", "name": "Validation"},
            {"code": "RA", "name": "Regulatory Affairs"},
            {"code": "RD", "name": "Research & Development"},
            {"code": "CS", "name": "Clinical & Safety"},
            {"code": "SC", "name": "Supply Chain"},
            {"code": "IT", "name": "IT & Systems"},
        ]
    }
