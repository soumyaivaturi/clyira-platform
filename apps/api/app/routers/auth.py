"""
Authentication & User Management Router — 21 CFR Part 11 compliant.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.audit import AuditLog
from app.models.base import generate_uuid
from app.models.user import User
from app.services import auth_service

router = APIRouter()

LOCKOUT_ATTEMPTS = 5       # failed attempts before lockout
LOCKOUT_MINUTES = 30       # lockout duration


# ── Audit helper ──────────────────────────────────────────────────────────────

async def _audit(
    db: AsyncSession,
    company_id: Optional[str],
    user_id: Optional[str],
    user_email: Optional[str],
    event_type: str,
    action: str = "AUTH",
    detail: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    entry = AuditLog(
        id=generate_uuid(),
        company_id=company_id or "system",
        user_id=user_id,
        user_email=user_email,
        event_type=event_type,
        action=action,
        detail=detail or {},
        ip_address=ip,
    )
    try:
        async with db.begin_nested():  # SAVEPOINT — rollback only affects this block
            db.add(entry)
            await db.flush()
    except Exception:
        pass  # savepoint rolled back; parent transaction and user state mutations are intact


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    company_id: str
    department: str | None = None
    onboarding_complete: bool = False
    terms_accepted_at: str | None = None
    force_password_change: bool = False

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_out(user: User, onboarding_complete: bool = False) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        company_id=user.company_id,
        department=user.department,
        onboarding_complete=onboarding_complete,
        terms_accepted_at=user.terms_accepted_at.isoformat() if user.terms_accepted_at else None,
        force_password_change=bool(user.force_password_change),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await auth_service.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    err = auth_service.validate_password_strength(data.password)
    if err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err)

    try:
        user = await auth_service.create_company_and_user(
            db,
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            company_name=data.company_name,
        )
    except Exception as exc:
        import traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {type(exc).__name__}: {exc}",
        ) from exc

    token = auth_service.create_access_token(user)
    return {"access_token": token, "user": _user_out(user)}


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else None

    user = await auth_service.get_user_by_email(db, data.email)
    if not user:
        # Don't reveal whether the email exists
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # Account lockout check (§11.300)
    if user.locked_until and user.locked_until > datetime.utcnow():
        remaining = max(1, int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1)
        await _audit(db, user.company_id, user.id, user.email, "login_attempt_locked",
                     detail={"remaining_minutes": remaining}, ip=ip)
        await db.commit()
        raise HTTPException(
            status_code=423,
            detail=f"Account locked due to too many failed attempts. Try again in {remaining} minute{'s' if remaining != 1 else ''}.",
        )

    if not auth_service.verify_password(data.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= LOCKOUT_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            await _audit(db, user.company_id, user.id, user.email, "account_locked",
                         detail={"attempts": user.failed_login_attempts, "locked_until_minutes": LOCKOUT_MINUTES}, ip=ip)
        else:
            remaining_before_lock = LOCKOUT_ATTEMPTS - user.failed_login_attempts
            await _audit(db, user.company_id, user.id, user.email, "login_failed",
                         detail={"attempts": user.failed_login_attempts,
                                 "remaining_before_lockout": remaining_before_lock}, ip=ip)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    # Successful login — reset lockout counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    await _audit(db, user.company_id, user.id, user.email, "login_success", ip=ip)
    await db.commit()

    token = auth_service.create_access_token(user)
    onboarding_complete = user.company.onboarding_complete if user.company else False
    return {"access_token": token, "user": _user_out(user, onboarding_complete)}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    onboarding_complete = current_user.company.onboarding_complete if current_user.company else False
    return _user_out(current_user, onboarding_complete)


@router.patch("/password", status_code=204)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not auth_service.verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    err = auth_service.validate_password_strength(data.new_password)
    if err:
        raise HTTPException(status_code=422, detail=err)

    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from the current password")

    history_ok = await auth_service.check_password_history(db, current_user.id, data.new_password)
    if not history_ok:
        raise HTTPException(status_code=400, detail="This password has been used recently. Please choose a different one.")

    await auth_service.save_password_history(db, current_user.id, current_user.password_hash)
    current_user.password_hash = auth_service.hash_password(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.force_password_change = False

    await _audit(db, current_user.company_id, current_user.id, current_user.email,
                 "password_changed", action="UPDATE")
    await db.commit()


@router.post("/accept-terms", status_code=204)
async def accept_terms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record that the user has read and accepted the System Use Policy (§11.10(j))."""
    current_user.terms_accepted_at = datetime.utcnow()
    await _audit(db, current_user.company_id, current_user.id, current_user.email,
                 "terms_accepted", action="AUTH", detail={"policy_version": "1.0"})
    await db.commit()
