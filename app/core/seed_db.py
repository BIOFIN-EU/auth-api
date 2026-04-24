from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Permission, Role

DEFAULT_ROLES = [
    {
        "name": "admin",
        "description": "Administrator role",
    },
    {
        "name": "user",
        "description": "Standard user role",
    },
]

DEFAULT_PERMISSIONS = [
    {
        "name": "users:read",
        "description": "Read users",
    },
    {
        "name": "users:write",
        "description": "Create/update users",
    },
    {
        "name": "roles:read",
        "description": "Read roles",
    },
    {
        "name": "roles:write",
        "description": "Create/update roles",
    },
    {
        "name": "permissions:read",
        "description": "Read permissions",
    },
    {
        "name": "permissions:write",
        "description": "Create/update permissions",
    },
]


async def seed_db(session: AsyncSession) -> None:
    await seed_roles(session)
    await seed_permissions(session)
    await session.commit()


async def seed_roles(session: AsyncSession) -> None:
    for role_data in DEFAULT_ROLES:
        result = await session.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        existing_role = result.scalar_one_or_none()

        if existing_role is None:
            session.add(Role(**role_data))


async def seed_permissions(session: AsyncSession) -> None:
    for permission_data in DEFAULT_PERMISSIONS:
        result = await session.execute(
            select(Permission).where(Permission.name == permission_data["name"])
        )
        existing_permission = result.scalar_one_or_none()

        if existing_permission is None:
            session.add(Permission(**permission_data))