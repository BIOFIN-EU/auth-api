from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from app.core.security import (
    create_access_token,
    create_refresh_expiry,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.core.settings import settings
from app.db.session import get_db
from app.deps.client_auth import verify_client
from app.models.models import RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(
    # Gateway/service auth: every /auth endpoint requires these headers
    # X-Client-ID, X-Client-Secret
    dependencies=[Security(verify_client)],
)

# User auth (JWT) for endpoints like /auth/me
bearer_scheme = HTTPBearer(auto_error=True)


def _get_bearer_token(creds: HTTPAuthorizationCredentials) -> str:
    if not creds or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return creds.credentials


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # ensure unique email among non-deleted users
    res = await db.execute(
        select(User).where(User.email == payload.email, User.deleted_at.is_(None))
    )
    if res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(User).where(User.email == payload.email, User.deleted_at.is_(None))
    )
    user: Optional[User] = res.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # collect roles
    roles = [role.name for role in user.roles if role.deleted_at is None]

    # collect permissions
    permissions = []
    for role in user.roles:
        if role.deleted_at is not None:
            continue
        for perm in role.permissions:
            permissions.append(perm.name)

    access = create_access_token(
        subject=str(user.id),
        roles=roles,
        permissions=list(set(permissions)),
    )

    refresh_plain = create_refresh_token()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_plain),
        expires_at=create_refresh_expiry(),
    )
    db.add(rt)
    await db.commit()

    return TokenPair(
        access_token=access,
        refresh_token=refresh_plain,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_h = hash_token(payload.refresh_token)
    now = datetime.now(timezone.utc)

    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_h,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    )
    rt: Optional[RefreshToken] = res.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # rotate refresh token: revoke old, issue new
    rt.revoked_at = now
    refresh_plain = create_refresh_token()
    new_rt = RefreshToken(
        user_id=rt.user_id,
        token_hash=hash_token(refresh_plain),
        expires_at=create_refresh_expiry(),
    )
    db.add(new_rt)

    # load user email as subject
    user_res = await db.execute(
        select(User).where(User.id == rt.user_id, User.deleted_at.is_(None))
    )
    user: Optional[User] = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    roles = [role.name for role in user.roles if role.deleted_at is None]

    permissions = []
    for role in user.roles:
        if role.deleted_at is not None:
            continue
        for perm in role.permissions:
            permissions.append(perm.name)

    access = create_access_token(
        subject=str(user.id),
        roles=roles,
        permissions=list(set(permissions)),
    )

    await db.commit()

    return TokenPair(
        access_token=access,
        refresh_token=refresh_plain,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
    )


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_h = hash_token(payload.refresh_token)
    now = datetime.now(timezone.utc)

    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_h,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rt: Optional[RefreshToken] = res.scalar_one_or_none()
    if rt:
        rt.revoked_at = now
        await db.commit()
    return None


@router.get("/me", response_model=UserOut)
async def me(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    token = _get_bearer_token(creds)

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    res = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = res.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.post("/change-password", status_code=204)
async def change_password(
        payload: ChangePasswordRequest,
        creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db),
):
    token = _get_bearer_token(creds)

    try:
        jwt_payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        email = jwt_payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    res = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user: Optional[User] = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Current password is incorrect",
                "field_errors": {
                    "current_password": "Current password is incorrect",
                },
            },
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "New password must be different",
                "field_errors": {
                    "new_password": "New password must be different from current password",
                },
            },
        )

    user.password_hash = hash_password(payload.new_password)

    now = datetime.now(timezone.utc)

    # Revoke all active refresh tokens for this user so existing sessions are logged out
    refresh_tokens_res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    refresh_tokens = refresh_tokens_res.scalars().all()

    for rt in refresh_tokens:
        rt.revoked_at = now

    await db.commit()

    return None
