"""
Auth Service — JWT creation/verification, password hashing, user management.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.company import Company
from app.models.user import User
from app.models.base import generate_uuid

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours — Part 11 §11.300 session control
PASSWORD_HISTORY_DEPTH = 5
ALGORITHM = "HS256"


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.id,
        "email": user.email,
        "company_id": user.company_id,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{generate_uuid()[:8]}"


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(
        select(User).options(selectinload(User.company)).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(
        select(User).options(selectinload(User.company)).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


def validate_password_strength(password: str) -> Optional[str]:
    """Returns an error message if the password is too weak, None if it passes. Part 11 §11.300."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password.encode()) > 72:
        return "Password must be 72 characters or fewer"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return "Password must contain at least one digit"
    return None


async def check_password_history(db: AsyncSession, user_id: str, new_password: str) -> bool:
    """Returns True if new_password is NOT in the last PASSWORD_HISTORY_DEPTH hashes (safe to use)."""
    from app.models.password_history import PasswordHistory
    result = await db.execute(
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(PASSWORD_HISTORY_DEPTH)
    )
    for entry in result.scalars().all():
        if verify_password(new_password, entry.password_hash):
            return False
    return True


async def save_password_history(db: AsyncSession, user_id: str, current_hash: str) -> None:
    """Store the current password hash before it is replaced, pruning history beyond the depth limit."""
    from app.models.password_history import PasswordHistory
    db.add(PasswordHistory(id=generate_uuid(), user_id=user_id, password_hash=current_hash))
    # Prune old entries beyond the depth limit
    result = await db.execute(
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.created_at.desc())
        .offset(PASSWORD_HISTORY_DEPTH)
    )
    for old in result.scalars().all():
        await db.delete(old)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def create_company_and_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    company_name: str,
) -> User:
    company = Company(
        id=generate_uuid(),
        name=company_name,
        slug=_slugify(company_name),
        sub_sectors=[],
        agencies=[],
        markets=[],
        certifications=[],
        settings={},
        onboarding_complete=False,
    )
    db.add(company)
    await db.flush()  # get company.id before creating user

    user = User(
        id=generate_uuid(),
        company_id=company.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="admin",  # first user in a company is admin
    )
    db.add(user)
    await db.flush()
    return user
