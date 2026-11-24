"""Drop the index of a person's numbers by kind and value

Revision ID: 0086
Revises: 0085
Create Date: 2026-11-23 20:00:00.000000

No query asks for a person's numbers by kind and value: they are read by the user (the
primary key) only (SQ-K06).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0086"
down_revision: str | None = "0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_user_identifiers_kind_value"), table_name="user_identifiers")


def downgrade() -> None:
    op.create_index(op.f("ix_user_identifiers_kind_value"), "user_identifiers", ["kind", "value"])
