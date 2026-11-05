"""Old mail records let go of what the mail said

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-05 21:00:00.000000

A mailbox's records beyond its latest 500 let go of what the mail's head said, sender, subject,
recipients and the rest (Tobi, 05.11.2026): the cleanup clears them and notes when
(`forgotten_at`). The rows stay, with their UIDs and Message-IDs, so that no mail is fetched
twice. The column has no keys, so SQLite adds it in place; the downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mail_records", sa.Column("forgotten_at", types.UtcDateTime(), nullable=True))


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("mail_records", "forgotten_at")
