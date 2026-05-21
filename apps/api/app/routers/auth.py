"""
Authentication & User Management Router
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import auth_service

router = APIRouter()


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

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await auth_service.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if len(data.password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")
    if len(data.password.encode()) > 72:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be 72 characters or fewer")

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
    return {
        "access_token": token,
        "user": UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            company_id=user.company_id,
            onboarding_complete=False,
        ),
    }


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.last_login = datetime.utcnow()
    await db.commit()

    token = auth_service.create_access_token(user)
    onboarding_complete = user.company.onboarding_complete if user.company else False
    return {
        "access_token": token,
        "user": UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            company_id=user.company_id,
            department=user.department,
            onboarding_complete=onboarding_complete,
        ),
    }


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    onboarding_complete = current_user.company.onboarding_complete if current_user.company else False
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        company_id=current_user.company_id,
        department=current_user.department,
        onboarding_complete=onboarding_complete,
    )
