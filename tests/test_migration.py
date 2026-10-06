"""
0002_users_v2 on a database as it was before migrations: old-style data
(mixed-case emails, project roles, users without roles) is brought up to
date. Uses its own throwaway database, auth_migrate_tmp.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.settings import settings

DB = "auth_migrate_tmp"
URL = settings.database_url.rsplit("/", 1)[0] + f"/{DB}"


def _sql(*statements: str):
    async def run():
        engine = create_async_engine(URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                results = [await conn.execute(text(s)) for s in statements]
                return [r.all() if r.returns_rows else None for r in results]
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _old_database():
    """The tables as the app created them before 0002, with old data."""
    async def run():
        from app.core.db import Base
        import app.models.models  # noqa: F401
        engine = create_async_engine(URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA IF EXISTS auth CASCADE"))
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
                await conn.execute(text("CREATE SCHEMA auth"))
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("ALTER TABLE auth.users DROP COLUMN display_name"))
        finally:
            await engine.dispose()
    asyncio.run(run())
    _sql(
        "INSERT INTO auth.roles (name) VALUES ('admin'), ('user'), ('borrower'), ('funder'), ('intermediary')",
        "INSERT INTO auth.users (email, password_hash) VALUES ('Jane.Smith@LPA.gov.uk', 'x'), ('bob@example.org', 'x')",
    )


def _upgrade() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, env={**os.environ, "POSTGRES_DB": DB},
    )


@pytest.fixture
def old_database():
    try:
        _old_database()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"No {DB} database: {exc}")


def test_upgrade_brings_old_data_up_to_date(old_database):
    result = _upgrade()
    assert result.returncode == 0, result.stderr
    emails, live_roles, user_roles = _sql(
        "SELECT email, display_name FROM auth.users ORDER BY email",
        "SELECT name FROM auth.roles WHERE deleted_at IS NULL ORDER BY name",
        "SELECT u.email, r.name FROM auth.user_roles ur JOIN auth.users u ON u.id = ur.user_id "
        "JOIN auth.roles r ON r.id = ur.role_id ORDER BY u.email",
    )
    assert emails == [("bob@example.org", None), ("jane.smith@lpa.gov.uk", None)]
    assert [name for (name,) in live_roles] == ["admin", "user"]
    assert user_roles == [("bob@example.org", "user"), ("jane.smith@lpa.gov.uk", "user")]
    # Running it again changes nothing.
    assert _upgrade().returncode == 0


def test_upgrade_stops_on_emails_that_differ_only_by_capitals(old_database):
    _sql("INSERT INTO auth.users (email, password_hash) VALUES ('BOB@example.org', 'x')")
    result = _upgrade()
    assert result.returncode != 0
    assert "BOB@example.org" in result.stderr and "bob@example.org" in result.stderr
