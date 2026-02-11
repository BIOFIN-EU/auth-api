from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError

from app.core.settings import settings
from app.db.session import get_db
from app.models.models import User


# JWT bearer scheme (NOT OAuth2)
bearer_scheme = HTTPBearer(auto_error=True)


def get_user_email_from_token_or_401(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        sub = payload.get("sub")
        if not sub:
            raise ValueError("Missing sub")
        return str(sub)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_user_by_email_or_401(db: AsyncSession, email: str) -> User:
    res = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive",
        )

    return user


def require_permission(permission_name: str):
    async def _dep(
        creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db),
    ):
        token = creds.credentials

        email = get_user_email_from_token_or_401(token)
        user = await get_user_by_email_or_401(db, email)

        # superuser bypass
        if user.is_superuser:
            return True

        perms = set()
        for role in user.roles:
            if role.deleted_at is not None:
                continue
            for perm in role.permissions:
                perms.add(perm.name)

        if permission_name not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden",
            )

        return True

    return _dep
