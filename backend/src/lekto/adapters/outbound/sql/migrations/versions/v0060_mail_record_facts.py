"""What a mail rule looks at in a fetched mail

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-04 23:00:00.000000

A fetched mail's record keeps the sender's and the recipients' addresses and names and the
names of the attachments Lekto takes, for the dry run of a mail rule over the latest mails.
Mails fetched before have none. The columns have no keys, so SQLite adds them in place; the
downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("senders", "recipients", "attachments")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(
            "mail_records",
            sa.Column(name, types.json_type(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    for name in reversed(COLUMNS):
        op.drop_column("mail_records", name)
