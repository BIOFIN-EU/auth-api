from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal, init_db
from app.core.security import hash_password
from app.core.seed_db import seed_db
from app.core.settings import settings
from app.models.models import Client
from app.routers.endpoints import api_router


app = FastAPI(title="Auth Service", version="1.0.0")

app.include_router(api_router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

    async with SessionLocal() as db:
        await seed_db(db)

        await seed_client(
            db,
            name="api-gateway",
            client_id=settings.GATEWAY_AUTH_CLIENT_ID,
            client_secret=settings.GATEWAY_AUTH_CLIENT_SECRET,
        )

        await seed_client(
            db,
            name="api-physical",
            client_id=settings.PHYSICAL_AUTH_CLIENT_ID,
            client_secret=settings.PHYSICAL_AUTH_CLIENT_SECRET,
        )


async def seed_client(
    db: AsyncSession,
    *,
    name: str,
    client_id: str,
    client_secret: str,
) -> None:
    result = await db.execute(
        select(Client).where(Client.client_id == client_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = name
        existing.client_secret_hash = hash_password(client_secret)
        existing.is_active = True
    else:
        db.add(
            Client(
                name=name,
                client_id=client_id,
                client_secret_hash=hash_password(client_secret),
                is_active=True,
            )
        )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()