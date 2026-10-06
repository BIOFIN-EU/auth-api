"""users: display name, lower-case emails, platform roles only

Revision ID: 0002_users_v2
Revises: 0001_baseline
Create Date: 2026-10-06 15:00:00.000000

- users.display_name: how other people see the user (optional).
- Emails in lower case, as the app now stores and compares them. Stops if
  two accounts differ only by capitals, listing them to resolve first.
- borrower / funder / intermediary are no longer platform roles (they are
  someone's part in a project, recorded by physical-api): retired.
- Every open account gets the "user" role, which new accounts now get at
  signup.

On a new database (no tables yet) there is nothing to change: the app
creates the tables on startup.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_users_v2"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "auth"
RETIRED_ROLES = ("borrower", "funder", "intermediary")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name, schema=S)


def upgrade() -> None:
    if not _has_table("users"):
        return
    bind = op.get_bind()

    columns = {c["name"] for c in sa.inspect(bind).get_columns("users", schema=S)}
    if "display_name" not in columns:
        op.add_column("users", sa.Column("display_name", sa.Text(), nullable=True), schema=S)

    clashes = bind.execute(sa.text(
        f"SELECT lower(trim(email)), string_agg(email, ', ') FROM {S}.users "
        "GROUP BY lower(trim(email)) HAVING count(*) > 1"
    )).all()
    if clashes:
        listed = "; ".join(emails for _, emails in clashes)
        raise RuntimeError(
            f"These accounts differ only by capitals, so emails can't be made lower case: {listed}. "
            "Close or rename all but one of each, then run the migration again."
        )
    bind.execute(sa.text(f"UPDATE {S}.users SET email = lower(trim(email)) WHERE email <> lower(trim(email))"))

    if _has_table("roles"):
        bind.execute(
            sa.text(f"UPDATE {S}.roles SET deleted_at = now() WHERE name = ANY(:names) AND deleted_at IS NULL"),
            {"names": list(RETIRED_ROLES)},
        )
        bind.execute(sa.text(
            f"INSERT INTO {S}.user_roles (user_id, role_id) "
            f"SELECT u.id, r.id FROM {S}.users u JOIN {S}.roles r ON r.name = 'user' AND r.deleted_at IS NULL "
            f"WHERE u.deleted_at IS NULL "
            f"AND NOT EXISTS (SELECT 1 FROM {S}.user_roles ur WHERE ur.user_id = u.id AND ur.role_id = r.id)"
        ))


def downgrade() -> None:
    """Emails stay lower case; the retired roles come back (unassigned)."""
    if not _has_table("users"):
        return
    op.drop_column("users", "display_name", schema=S)
    op.get_bind().execute(
        sa.text(f"UPDATE {S}.roles SET deleted_at = NULL WHERE name = ANY(:names)"),
        {"names": list(RETIRED_ROLES)},
    )
