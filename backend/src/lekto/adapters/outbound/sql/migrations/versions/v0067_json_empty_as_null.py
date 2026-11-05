"""An empty JSON value is SQL NULL

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-05 23:00:00.000000

A JSON column held two kinds of empty: SQL NULL where the code wrote `null()`, and the JSON
`null`, which the column type wrote for `None`. Both read back as `None`, but only one answers
`IS NULL`. The type writes `None` as SQL NULL from now on (Tobi, 05.11.2026); this turns the
stored JSON `null` of every JSON column that may be empty into NULL. The downgrade leaves NULL,
which the type read as `None` before as well.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS: tuple[tuple[str, str], ...] = (
    ("contact_identifiers", "learned_in"),
    ("processing_log", "reasons"),
    ("rules", "disabled_reasons"),
    ("jobs", "result"),
    ("mailboxes", "error"),
    ("mailboxes", "skipped"),
    ("mailboxes", "step_failed"),
    ("mail_records", "reason"),
    ("mail_records", "keywords"),
    ("mail_origins", "keywords"),
    ("mail_rules", "conditions"),
    ("mail_rules", "disabled_reason"),
    ("tasks", "step"),
    ("tasks", "answer"),
    ("tasks", "reason"),
)
"""The JSON columns that may be empty, as of this revision."""


def upgrade() -> None:
    for table_name, column_name in COLUMNS:
        column = sa.column(column_name, types.json_type())
        table = sa.table(table_name, column)
        op.execute(
            sa.update(table)
            .where(sa.cast(column, sa.Text) == "null")
            .values({column_name: sa.null()})
        )


def downgrade() -> None:
    pass
