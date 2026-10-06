"""
Platform roles held by a user (admin, user). A user's roles are copied into
their access token, so a change applies from their next token renewal (at
most ACCESS_TOKEN_EXPIRE_MINUTES later) or next login.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Role, User, UserRole

DEFAULT_ROLE = "user"


class RoleError(ValueError):
    pass


async def active_role(db: AsyncSession, name: str) -> Role:
    role = await db.scalar(select(Role).where(Role.name == name, Role.deleted_at.is_(None)))
    if role is None:
        names = (await db.scalars(select(Role.name).where(Role.deleted_at.is_(None)).order_by(Role.name))).all()
        raise RoleError(f"No role '{name}'. Roles: {', '.join(names)}")
    return role


async def grant_role(db: AsyncSession, user: User, name: str) -> bool:
    """Give the user the role; False if they already have it. Not committed."""
    role = await active_role(db, name)
    held = await db.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id))
    if held is not None:
        return False
    db.add(UserRole(user_id=user.id, role_id=role.id))
    return True


async def revoke_role(db: AsyncSession, user: User, name: str) -> bool:
    """Take the role away; False if they didn't have it. Not committed."""
    role = await active_role(db, name)
    held = await db.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id))
    if held is None:
        return False
    await db.delete(held)
    return True


def token_claims(user: User) -> tuple[list[str], list[str]]:
    """(roles, permissions) for the user's access token: active roles only."""
    roles = [role for role in user.roles if role.deleted_at is None]
    permissions = {permission.name for role in roles for permission in role.permissions}
    return sorted(role.name for role in roles), sorted(permissions)
