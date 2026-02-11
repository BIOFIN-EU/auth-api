from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.db.session import SessionLocal
from app.models.models import User, Role, UserRole
from app.core.security import hash_password

async def bootstrap_admin():
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return

    async with SessionLocal() as db:  # type: AsyncSession
        res = await db.execute(select(User).where(User.email == settings.BOOTSTRAP_ADMIN_EMAIL))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Ensure admin role assigned (if exists)
        role_res = await db.execute(select(Role).where(Role.name == "admin"))
        admin_role = role_res.scalar_one_or_none()
        if admin_role:
            link = await db.execute(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id))
            if not link.scalar_one_or_none():
                db.add(UserRole(user_id=user.id, role_id=admin_role.id))
                await db.commit()
