"""What a person wants to be told about, and the documents waiting for their next notification

Revision ID: 0070
Revises: 0069
Create Date: 2026-11-07 09:00:00.000000

Per user (Tobi, 06.11.2026): the kinds of notifications switched on (JSON list), whether the
titles of documents stand in them, and the documents that came to wait in their inbox since the
last notification (JSON list of ids, at most 50). A user without a row has every kind on and the
titles shown. The table is new; the downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0070"
down_revision: str | None = "0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kinds", types.json_type(), nullable=False),
        sa.Column("titles", sa.Boolean(), nullable=False),
        sa.Column("pending", types.json_type(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("push_preferences")
