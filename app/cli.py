"""
Manage users' platform roles from the command line, e.g. on the server:

    docker compose exec auth-api python -m app.cli grant-role you@example.com admin
    docker compose exec auth-api python -m app.cli revoke-role you@example.com admin
    docker compose exec auth-api python -m app.cli show-roles you@example.com

A change applies from the user's next token renewal (within
ACCESS_TOKEN_EXPIRE_MINUTES) or next login.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models.models import User
from app.schemas.auth import normalise_email
from app.services.user_roles import RoleError, grant_role, revoke_role, token_claims


async def run(command: str, email: str, role: str | None) -> int:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == normalise_email(email), User.deleted_at.is_(None)))
        if user is None:
            print(f"No open account for {email}", file=sys.stderr)
            return 1
        try:
            if command == "grant-role":
                changed = await grant_role(db, user, role)
                print(f"{email} now has '{role}'" if changed else f"{email} already had '{role}'")
            elif command == "revoke-role":
                changed = await revoke_role(db, user, role)
                print(f"'{role}' taken from {email}" if changed else f"{email} didn't have '{role}'")
        except RoleError as exc:
            print(exc, file=sys.stderr)
            return 1
        await db.commit()
        await db.refresh(user)
        roles, permissions = token_claims(user)
        print(f"{email}: roles {roles or 'none'}; permissions {permissions or 'none'}")
    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Users' platform roles")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, needs_role in (("grant-role", True), ("revoke-role", True), ("show-roles", False)):
        sub = commands.add_parser(name)
        sub.add_argument("email")
        if needs_role:
            sub.add_argument("role", help="e.g. admin")
    args = parser.parse_args()
    return asyncio.run(run(args.command, args.email, getattr(args, "role", None)))


if __name__ == "__main__":
    sys.exit(main())
