from fastapi import Request, HTTPException, status, Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import Client
from app.core.security import verify_password


# 🔑 IMPORTANT: give each header a unique scheme_name
client_id_header = APIKeyHeader(
    name="X-Client-ID",
    scheme_name="Client ID"
)

client_secret_header = APIKeyHeader(
    name="X-Client-Secret",
    scheme_name="Client Secret"
)


async def verify_client(
    client_id: str = Security(client_id_header),
    client_secret: str = Security(client_secret_header),
    db: AsyncSession = Depends(get_db),
):
    if not client_id or not client_secret:
        raise HTTPException(status_code=401, detail="Missing client credentials")

    result = await db.execute(
        select(Client).where(Client.client_id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client or not verify_password(client_secret, client.client_secret_hash):
        raise HTTPException(status_code=401, detail="Invalid client")

    return client
