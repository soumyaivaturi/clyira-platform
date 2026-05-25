"""
Shared FastAPI dependencies — auth, DB session, RBAC role enforcement.
"""
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services import auth_service

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = auth_service.decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = await auth_service.get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return user


def require_roles(*allowed_roles: str) -> Callable:
    """
    Dependency factory — raises 403 if the current user's role is not in allowed_roles.

    Usage:
        @router.delete("/{id}", dependencies=[Depends(require_roles("admin", "qa_lead"))])
        async def delete_something(...):
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )
        return current_user
    return _check


# ── Named role dependencies ───────────────────────────────────────────────────
# Use these in router Depends() calls for consistent, readable enforcement.

require_admin = require_roles("admin")
require_qa_or_above = require_roles("admin", "qa_lead")
require_approver_or_above = require_roles("admin", "qa_lead", "approver")
require_write_access = require_roles("admin", "qa_lead", "author", "approver", "reviewer", "auditor", "sme")
