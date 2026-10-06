"""baseline: the tables as the app created them before migrations

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-06 15:00:00.000000

Nothing to do: until now the app created its tables itself on startup, and
still does for a new database. Later revisions change existing tables.
"""
from typing import Sequence, Union

revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
