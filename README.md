# Auth Microservice (Production-ready) — FastAPI + PostgreSQL

Basic Requirements:
- email-only login
- JWT access + refresh tokens (stored server-side)
- roles + permissions (RBAC)
- soft delete
- ready for real deployment with Docker

## What’s included
- `auth-api/` FastAPI service (Gunicorn+Uvicorn)
- `auth-postgres` PostgreSQL service (schema created via init SQL)
- `/auth` endpoints:
  - `POST /auth/register`
  - `POST /auth/login`
  - `POST /auth/refresh` (rotates refresh token)
  - `POST /auth/logout`
  - `GET /auth/me`
- `/rbac` endpoints (permission-protected):
  - `POST /rbac/roles`
  - `POST /rbac/permissions`
  - `POST /rbac/users/{email}/roles`
  - `POST /rbac/roles/{role}/permissions`

> Bootstrap admin user is created on API startup if `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD` are set.

## Run (production compose)
1) Create env:
```bash
cp .env.prod.example .env.prod
# edit .env.prod (set strong passwords + keep JWT secret)
```

2) Start:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Notes
- Access token expiry: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`); clients renew it with the refresh token
- Refresh token expiry: 24h (configurable via `REFRESH_TOKEN_EXPIRE_HOURS`)
- Refresh tokens are **stored hashed** in DB and rotated on refresh.

## Database migrations
The app creates missing tables on startup; changes to existing tables are
Alembic migrations (`alembic/versions`). Run them before starting new code:

```bash
docker compose run --rm auth-api alembic upgrade head
```

## Platform roles
Every account has `user` (given at signup). `admin` is given from the
command line, e.g. on the server:

```bash
docker compose exec auth-api python -m app.cli grant-role you@example.com admin
docker compose exec auth-api python -m app.cli revoke-role you@example.com admin
docker compose exec auth-api python -m app.cli show-roles you@example.com
```

Roles are copied into the access token, so a change applies from the
user's next token renewal (within `ACCESS_TOKEN_EXPIRE_MINUTES`) or login.
Someone's part in a project (borrower, funder, landowner, ...) is not a
platform role: physical-api records it per project.

## Tests
Against throwaway databases only (see `tests/conftest.py` for the commands).
