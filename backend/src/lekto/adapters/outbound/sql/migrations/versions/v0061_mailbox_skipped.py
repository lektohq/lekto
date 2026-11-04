"""The latest mail a mailbox left out

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-05 10:00:00.000000

A mailbox keeps when and which mail it last left out because it was too large (the limit
follows `LEKTO_UPLOAD_MAX_SIZE`), to show it at the mailbox. None after the update. The columns
have no keys, so SQLite adds them in place; the downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mailboxes", sa.Column("skipped_at", types.UtcDateTime(), nullable=True))
    op.add_column("mailboxes", sa.Column("skipped", types.json_type(), nullable=True))


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("mailboxes", "skipped")
    op.drop_column("mailboxes", "skipped_at")
