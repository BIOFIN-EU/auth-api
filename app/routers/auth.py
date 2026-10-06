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
from app.models.models import Client, RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateMeRequest,
    UserLookupRequest,
    UserOut,
    UserSummary,
    normalise_email,
)
from app.services.user_roles import DEFAULT_ROLE, grant_role, token_claims
import logging

logger = logging.getLogger(__name__)


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


async def _current_user_or_401(creds: HTTPAuthorizationCredentials, db: AsyncSession) -> User:
    """The open account the access token is for."""
    try:
        payload = jwt.decode(_get_bearer_token(creds), settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = payload.get("sub")
    user = await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None))) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    return user


@router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Emails are unique across all accounts, closed ones included.
    res = await db.execute(select(User).where(User.email == payload.email))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await grant_role(db, user, DEFAULT_ROLE)
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

    roles, permissions = token_claims(user)
    access = create_access_token(subject=str(user.id), roles=roles, permissions=permissions)

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
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_MINUTES / 60,
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

    # load user and issue access token with user.id as subject
    user_res = await db.execute(
        select(User).where(User.id == rt.user_id, User.deleted_at.is_(None))
    )
    user: Optional[User] = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    roles, permissions = token_claims(user)
    access = create_access_token(subject=str(user.id), roles=roles, permissions=permissions)

    await db.commit()

    return TokenPair(
        access_token=access,
        refresh_token=refresh_plain,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        expires_in_hours=settings.ACCESS_TOKEN_EXPIRE_MINUTES / 60,
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


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UpdateMeRequest,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """The user's own details: their display name (blank removes it)."""
    user = await _current_user_or_401(creds, db)
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    await db.commit()
    await db.refresh(user)
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
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    res = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
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

@router.post("/close-account", status_code=204)
async def close_account(
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
        user_id = jwt_payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    res = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user: Optional[User] = res.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")

    now = datetime.now(timezone.utc)
    user.is_active = False
    user.deleted_at = now

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


async def require_physical_client(client: Client = Security(verify_client)) -> Client:
    """
    For physical-api only. The gateway forwards users' requests with its own
    client credentials, so its client must not be enough: anyone could look
    up who has an account.
    """
    if client.client_id != settings.PHYSICAL_AUTH_CLIENT_ID:
        raise HTTPException(status_code=403, detail="Not available to this client")
    return client


@router.post("/users/lookup", response_model=list[UserSummary], dependencies=[Depends(require_physical_client)])
async def lookup_users(payload: UserLookupRequest, db: AsyncSession = Depends(get_db)):
    """
    Email and display name of each of these users (physical-api showing a
    project's members). Closed accounts and unknown ids are left out.
    """
    if not payload.ids:
        return []
    result = await db.execute(
        select(User).where(User.id.in_(payload.ids), User.deleted_at.is_(None), User.is_active.is_(True))
    )
    return [UserSummary(id=u.id, email=u.email, display_name=u.display_name) for u in result.scalars()]


@router.get("/users/by-email", dependencies=[Depends(require_physical_client)])
async def get_user_by_email(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """physical-api adding a project member. Closed accounts can't be added."""
    logger.info("Fetching user by email")

    result = await db.execute(
        select(User).where(
            User.email == normalise_email(email), User.deleted_at.is_(None), User.is_active.is_(True)
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
    }