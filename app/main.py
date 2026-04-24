from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.routers.endpoints import api_router
from app.models.models import Client
from app.core.security import hash_password
from app.core.settings import settings
from app.core.db import SessionLocal, init_db
from app.core.seed_db import seed_db


app = FastAPI(title="Auth Service", version="1.0.0")

app.include_router(api_router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

    async with SessionLocal() as db:
        await seed_db(db)
        await seed_gateway_client(db)


async def seed_gateway_client(db: AsyncSession) -> None:
    result = await db.execute(
        select(Client).where(Client.client_id == settings.AUTH_CLIENT_ID)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.client_secret_hash = hash_password(settings.AUTH_CLIENT_SECRET)
        existing.is_active = True
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