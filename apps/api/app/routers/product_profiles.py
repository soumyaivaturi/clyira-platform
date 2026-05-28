"""
Product Profiles — per-product classification defaults + MBR template memory.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.product_profile import ProductProfile
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProductProfileCreate(BaseModel):
    profile_name: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    dosage_form: Optional[str] = None
    manufacturing_site: Optional[str] = None
    record_family: str = "pharma_bpr"
    product_type: str = "small_molecule"
    is_sterile: bool = False
    manufacturing_context: str = "internal"
    batch_purpose: str = "commercial"
    target_markets: list[str] = []


class ProductProfileUpdate(BaseModel):
    profile_name: Optional[str] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    dosage_form: Optional[str] = None
    manufacturing_site: Optional[str] = None
    record_family: Optional[str] = None
    product_type: Optional[str] = None
    is_sterile: Optional[bool] = None
    manufacturing_context: Optional[str] = None
    batch_purpose: Optional[str] = None
    target_markets: Optional[list[str]] = None
    active: Optional[bool] = None


# ── Serialiser ────────────────────────────────────────────────────────────────

def _profile_out(p: ProductProfile) -> dict:
    return {
        "id": p.id,
        "company_id": p.company_id,
        "created_by": p.created_by,
        "profile_name": p.profile_name,
        "product_code": p.product_code,
        "product_name": p.product_name,
        "dosage_form": p.dosage_form,
        "manufacturing_site": p.manufacturing_site,
        "classification": {
            "record_family": p.record_family,
            "product_type": p.product_type,
            "is_sterile": p.is_sterile,
            "manufacturing_context": p.manufacturing_context,
            "batch_purpose": p.batch_purpose,
            "target_markets": p.target_markets or [],
        },
        "template": {
            "document_id": p.template_document_id,
            "required_fields": p.template_required_fields,
            "acceptance_criteria": p.template_acceptance_criteria,
            "section_count": p.template_section_count,
            "analyzed_at": p.template_analyzed_at,
        },
        "spec_document_ids": p.spec_document_ids or [],
        "active": p.active,
        "created_at": str(p.created_at),
        "updated_at": str(p.updated_at),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_product_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active product profiles for this company."""
    result = await db.execute(
        select(ProductProfile)
        .where(ProductProfile.company_id == current_user.company_id)
        .where(ProductProfile.active == True)  # noqa: E712
        .order_by(ProductProfile.profile_name)
    )
    return [_profile_out(p) for p in result.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product_profile(
    body: ProductProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a product profile to remember classification defaults for a product line."""
    profile = ProductProfile(
        company_id=current_user.company_id,
        created_by=current_user.id,
        profile_name=body.profile_name,
        product_code=body.product_code,
        product_name=body.product_name,
        dosage_form=body.dosage_form,
        manufacturing_site=body.manufacturing_site,
        record_family=body.record_family,
        product_type=body.product_type,
        is_sterile=body.is_sterile,
        manufacturing_context=body.manufacturing_context,
        batch_purpose=body.batch_purpose,
        target_markets=body.target_markets,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _profile_out(profile)


@router.get("/{profile_id}")
async def get_product_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await db.get(ProductProfile, profile_id)
    if not profile or profile.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _profile_out(profile)


@router.patch("/{profile_id}")
async def update_product_profile(
    profile_id: str,
    body: ProductProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await db.get(ProductProfile, profile_id)
    if not profile or profile.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Profile not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return _profile_out(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await db.get(ProductProfile, profile_id)
    if not profile or profile.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.active = False
    await db.commit()


@router.post("/{profile_id}/analyze-template")
async def analyze_mbr_template(
    profile_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a blank MBR template (PDF/DOCX). Clyira extracts the required field
    names and any in-line acceptance criteria, stores them against this profile.
    Future dossiers using this profile get a richer completeness checklist.
    """
    from app.services.bpr_extraction_service import extract_template_fields
    from app.services.document_service import DocumentService

    profile = await db.get(ProductProfile, profile_id)
    if not profile or profile.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Profile not found")

    content = await file.read()
    filename = file.filename or "template"
    file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    # Extract text
    svc = DocumentService.__new__(DocumentService)
    extracted_text = await svc._extract_text_from_bytes(content, file_type)

    if not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from the template. Ensure it is a readable PDF or DOCX."
        )

    template_data = extract_template_fields(extracted_text)

    # Persist the template document so it's accessible later
    doc_svc = DocumentService(db)
    try:
        doc = await doc_svc.upload_document(
            file_content=content,
            filename=filename,
            company_id=current_user.company_id,
            user_id=current_user.id,
            metadata={
                "title": f"MBR Template — {profile.profile_name}",
                "document_category": "MBR",
            },
        )
        template_doc_id = doc.id
    except Exception as e:
        # Duplicate or storage error — proceed without storing the doc
        logger.warning(f"Template document upload skipped: {e}")
        template_doc_id = profile.template_document_id

    profile.template_document_id = template_doc_id
    profile.template_required_fields = template_data["required_fields"]
    profile.template_acceptance_criteria = template_data["acceptance_criteria"]
    profile.template_section_count = str(template_data["section_count"])
    profile.template_analyzed_at = datetime.now(timezone.utc).isoformat()

    await db.commit()
    await db.refresh(profile)

    return {
        "profile_id": profile_id,
        "template_document_id": template_doc_id,
        "required_fields_count": len(template_data["required_fields"]),
        "acceptance_criteria_count": len(template_data["acceptance_criteria"]),
        "section_count": template_data["section_count"],
        "sample_fields": template_data["required_fields"][:10],
        "analyzed_at": profile.template_analyzed_at,
    }


@router.post("/{profile_id}/add-spec-document")
async def add_spec_document(
    profile_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Link an already-uploaded document (CPP, specification, method) to this profile
    as a reference for acceptance criteria.
    """
    from app.models.document import Document

    profile = await db.get(ProductProfile, profile_id)
    if not profile or profile.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Profile not found")

    document_id = body.get("document_id", "").strip()
    if not document_id:
        raise HTTPException(status_code=422, detail="document_id required")

    doc = await db.get(Document, document_id)
    if not doc or doc.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Document not found")

    ids: list = list(profile.spec_document_ids or [])
    if document_id not in ids:
        ids.append(document_id)
        profile.spec_document_ids = ids
        await db.commit()

    return {"profile_id": profile_id, "spec_document_ids": profile.spec_document_ids}
