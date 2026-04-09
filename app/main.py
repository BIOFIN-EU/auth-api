from fastapi import FastAPI
from app.routers.endpoints import api_router
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.models.models import Client
from app.core.security import hash_password
from app.core.settings import settings
from app.db.session import SessionLocal, engine
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Auth Service", version="1.0.0")

app.include_router(api_router)


@app.on_event("startup")
async def db_startup():
    """Create tables on startup if they don't exist"""
    # Create the auth schema first (THIS IS THE KEY FIX)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        logger.info("Schema 'auth' created or already exists")


    logger.info("Creating database tables if they don't exist...")

    # Import models so they are registered with Base
    from app.models.models import Base

    # Create all tables
    async with engine.begin() as conn:
       await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready!")

    # Test database connection
    try:
        async with SessionLocal() as db:
            await db.execute(text("SELECT 1"))
            logger.info("Database connection successful!")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    # Seed the gateway client
    await seed_gateway_client()




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
