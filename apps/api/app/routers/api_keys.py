"""
API Keys Router — create, list, and revoke API keys for external integrations.
Keys are shown in full exactly once on creation; thereafter only the prefix is exposed.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.api_key import APIKey
from app.models.base import generate_uuid
from app.models.user import User
from app.services.auth_service import hash_password

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateKeyRequest(BaseModel):
    name: str
    integration_type: Optional[str] = None  # mes, lims, vlms, qms, erp, custom


class APIKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    integration_type: Optional[str]
    created_at: Optional[str]
    last_used_at: Optional[str]
    is_active: bool


class CreatedKeyOut(APIKeyOut):
    key: str  # full key — returned only on creation, never again


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_key() -> tuple[str, str, str]:
    """Return (full_key, display_prefix, bcrypt_hash)."""
    token = secrets.token_hex(16)          # 32 hex chars
    full_key = f"clyr_{token}"             # clyr_ + 32 chars = 37 total
    prefix = f"clyr_{token[:8]}"           # clyr_ + first 8 = shown in UI
    return full_key, prefix, hash_password(full_key)


def _key_out(k: APIKey) -> APIKeyOut:
    return APIKeyOut(
        id=k.id,
        name=k.name,
        key_prefix=k.key_prefix,
        integration_type=k.integration_type,
        created_at=k.created_at.isoformat() if k.created_at else None,
        last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
        is_active=k.is_active,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[APIKeyOut])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey)
        .where(APIKey.company_id == current_user.company_id, APIKey.is_active == True)
        .order_by(APIKey.created_at.desc())
    )
    return [_key_out(k) for k in result.scalars().all()]


@router.post("", response_model=CreatedKeyOut, status_code=201)
async def create_api_key(
    data: CreateKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Key name is required")

    full_key, prefix, key_hash = _generate_key()

    api_key = APIKey(
        id=generate_uuid(),
        company_id=current_user.company_id,
        user_id=current_user.id,
        name=data.name.strip(),
        key_prefix=prefix,
        key_hash=key_hash,
        integration_type=data.integration_type or None,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return CreatedKeyOut(**_key_out(api_key).model_dump(), key=full_key)


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key = await db.get(APIKey, key_id)
    if not api_key or api_key.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="API key not found")
    api_key.is_active = False
    await db.commit()
