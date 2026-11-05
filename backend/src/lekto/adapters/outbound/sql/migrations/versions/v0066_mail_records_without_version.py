"""Mail records and origins without a version

Revision ID: 0066
Revises: 0065
Create Date: 2026-11-05 22:00:00.000000

The records of fetched mails and the origins of documents are only ever inserted; their
`version`, which optimistic locking counts on the tables that change, was never read (Tobi,
05.11.2026). The columns go; the downgrade adds them back at 0. They have no keys, so SQLite
drops and adds them in place.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066"
down_revision: str | None = "0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("mail_records", "mail_origins")


def upgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "version")


def downgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        if op.get_bind().dialect.name != "sqlite":  # SQLite keeps the default; harmless
            op.alter_column(table, "version", existing_type=sa.Integer(), server_default=None)
