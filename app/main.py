from fastapi import FastAPI
from app.routers.endpoints import api_router
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.models import Client
from app.core.security import hash_password
from app.core.settings import settings
from app.db.session import SessionLocal

app = FastAPI(title="Auth Service", version="1.0.0")

app.include_router(api_router)


@app.on_event("startup")
async def seed_gateway_client():
    async with SessionLocal() as db:

        result = await db.execute(
            select(Client).where(Client.client_id == settings.AUTH_CLIENT_ID)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.client_secret_hash = hash_password(settings.AUTH_CLIENT_SECRET)
            await db.commit()
            return

        try:
            client = Client(
                name="api-gateway",
                client_id=settings.AUTH_CLIENT_ID,
                client_secret_hash=hash_password(settings.AUTH_CLIENT_SECRET),
                is_active=True,
            )
            db.add(client)
            await db.commit()

        except IntegrityError:
            await db.rollback()
