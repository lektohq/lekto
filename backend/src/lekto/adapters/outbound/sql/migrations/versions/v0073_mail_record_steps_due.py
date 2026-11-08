"""Mail records keep the steps on the server still to run

Revision ID: 0073
Revises: 0072
Create Date: 2026-11-08 10:00:00.000000

A mail's record was stored before the steps on the server ran (mark it read, move it), so a
fetch interrupted in between left them undone for good: the mail counts as fetched and is not
fetched again. `mail_records` keeps the steps still to run with what became of the mail
(`steps_due`, JSON; NULL: none), the next fetch runs them. The records before have none. The
column has no key, so SQLite adds it in place; the downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mail_records", sa.Column("steps_due", types.json_type(), nullable=True))


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("mail_records", "steps_due")
