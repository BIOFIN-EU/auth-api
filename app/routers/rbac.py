from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import User, Role, Permission, UserRole, RolePermission
from app.schemas.rbac import CreateRole, CreatePermission, AssignRole, AssignPermissionToRole
from app.schemas.auth import RoleOut, PermissionOut
from app.services.rbac_service import require_permission


router = APIRouter()


@router.post("/roles", response_model=RoleOut, dependencies=[Depends(require_permission("roles:write"))])
async def create_role(payload: CreateRole, db: AsyncSession = Depends(get_db)):
    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Role exists or invalid")
    await db.refresh(role)
    return role


@router.post("/permissions", response_model=PermissionOut, dependencies=[Depends(require_permission("permissions:write"))])
async def create_permission(payload: CreatePermission, db: AsyncSession = Depends(get_db)):
    perm = Permission(name=payload.name, description=payload.description)
    db.add(perm)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Permission exists or invalid")
    await db.refresh(perm)
    return perm


@router.post("/users/{user_email}/roles", status_code=204, dependencies=[Depends(require_permission("users:write"))])
async def assign_role(user_email: str, payload: AssignRole, db: AsyncSession = Depends(get_db)):
    user_res = await db.execute(select(User).where(User.email == user_email, User.deleted_at.is_(None)))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_res = await db.execute(select(Role).where(Role.name == payload.role_name, Role.deleted_at.is_(None)))
    role = role_res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    exists = await db.execute(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id))
    if not exists.scalar_one_or_none():
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
    return None


@router.post("/roles/{role_name}/permissions", status_code=204, dependencies=[Depends(require_permission("roles:write"))])
async def assign_permission(role_name: str, payload: AssignPermissionToRole, db: AsyncSession = Depends(get_db)):
    role_res = await db.execute(select(Role).where(Role.name == role_name, Role.deleted_at.is_(None)))
    role = role_res.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    perm_res = await db.execute(select(Permission).where(Permission.name == payload.permission_name))
    perm = perm_res.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    exists = await db.execute(select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.permission_id == perm.id))
    if not exists.scalar_one_or_none():
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
        await db.commit()
    return None
