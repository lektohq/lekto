"""Sessions, API tokens, known devices, external identities and failed sign-ins without a version

Revision ID: 0079
Revises: 0078
Create Date: 2026-11-19 12:00:00.000000

These rows are only added, touched (a timestamp) and removed; their `version`, which
optimistic locking counts on the tables that change, was never checked (the one of the
failed sign-ins only counted up). The columns go, as in revision 0066; the downgrade adds
them back at 1 (on SQLite by copying the table, which keeps a default otherwise). They have
no keys, so SQLite drops them in place (SQ-04).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0079"
down_revision: str | None = "0078"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("sessions", "api_tokens", "known_devices", "external_identities", "login_failures")


def upgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "version")


def downgrade() -> None:
    sqlite = op.get_bind().dialect.name == "sqlite"
    for table in _TABLES:
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if not sqlite:
            op.alter_column(table, "version", existing_type=sa.Integer(), server_default=None)
            continue
        # SQLite keeps a column's default: the table is copied anew without it, as the earlier
        # revisions made it. No table refers to these five, so copying loses nothing.
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.alter_column(
                "version", existing_type=sa.Integer(), existing_nullable=False, server_default=None
            )
