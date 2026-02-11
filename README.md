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
- Access token expiry: 24h (configurable via `ACCESS_TOKEN_EXPIRE_HOURS`)
- Refresh token expiry: 24h (configurable via `REFRESH_TOKEN_EXPIRE_HOURS`)
- Refresh tokens are **stored hashed** in DB and rotated on refresh.
