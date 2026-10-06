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
Alembic migrations (`alembic/versions`). When a deploy includes one, stop the
service, migrate, then start the new code:

```bash
docker compose pull auth-api
docker compose stop auth-api
docker compose run --rm auth-api alembic upgrade head
docker compose up -d auth-api
```

Logins and token renewals pause for those seconds; signed-in users carry on
(the gateway checks their tokens itself).

## Managing platform roles
Platform roles say what someone may do on the dashboard as a whole:

| Role | Who has it | What it's for |
|---|---|---|
| `user` | every account (given at signup) | using the dashboard: creating projects, being added to others |
| `admin` | given by hand (below) | running the platform: support access to projects, lookup lists, the intermediary register |

Someone's part in a project (borrower, funder, landowner, ecologist, ...) is
not a platform role: physical-api records it per project, on the project's
Access tab.

### Giving or taking away a role
Run the command inside the auth-api container. On the server, from the
folder with the deploy `docker-compose.yml`:

```bash
# give someone admin
docker compose exec auth-api python -m app.cli grant-role someone@example.org admin

# take it away again
docker compose exec auth-api python -m app.cli revoke-role someone@example.org admin

# see what they have
docker compose exec auth-api python -m app.cli show-roles someone@example.org
```

Locally, run the same commands from this repository's folder (its
`docker-compose.yml` names the container `auth-api` too).

Each command prints the account's roles and permissions afterwards, e.g.:

```
someone@example.org now has 'admin'
someone@example.org: roles ['admin', 'user']; permissions ['permissions:read', ...]
```

- The email is matched without regard to capitals.
- The account must exist and be open: people sign up on the dashboard first.
- An unknown role is refused, with the list of roles that exist.
- Giving a role someone already has (or taking one they don't have) changes
  nothing and says so.

### When a change applies
Roles are copied into the user's access token, so a change applies at their
next token renewal (within `ACCESS_TOKEN_EXPIRE_MINUTES`, 30 by default) or
straight away if they log out and in again.

### Adding a new platform role
Add it to `DEFAULT_ROLES` in `app/core/seed_db.py` (created on startup), then
give it with the commands above. Only add roles about the platform as a
whole; anything about a project belongs in physical-api.

## Tests
Against throwaway databases only (see `tests/conftest.py` for the commands).
