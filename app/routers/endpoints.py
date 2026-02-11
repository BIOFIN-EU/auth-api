from fastapi import APIRouter
from app.routers import auth, rbac


api_router = APIRouter()

std_prefix = '/api'

api_router.include_router(auth.router,
                          prefix=f"{std_prefix}/auth",
                          tags=["Auth"])

api_router.include_router(rbac.router,
                          prefix=f"{std_prefix}/rbac",
                          tags=["Roles"])
