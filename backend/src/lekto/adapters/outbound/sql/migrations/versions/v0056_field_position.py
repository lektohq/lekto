"""Where a field stands among the fields

Revision ID: 0056
Revises: 0055
Create Date: 2026-11-03 12:00:00.000000

A field carries a position (Tobi, 03.11.2026): fields are listed by it, smaller first, the same
by name. Fields from before get 0, so they stay in the order of their names.

The column has no keys, so SQLite adds it in place. The downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "field_definitions",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("field_definitions", "position")
