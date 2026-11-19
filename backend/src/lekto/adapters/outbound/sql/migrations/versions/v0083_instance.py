"""The instance's id

Revision ID: 0083
Revises: 0082
Create Date: 2026-11-19 20:00:00.000000

Lekto gets a stable id of its instance (Tobi, 19.11.2026,
`.knowledge/open/instance-id-fas.md`): random (UUIDv4, no time in it), made once here and kept
in the database, so that a restore keeps it. Home Assistant tells instances apart by it.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083"
down_revision: str | None = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    instance = op.create_table(
        "instance",
        sa.Column("key", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_instance")),
    )
    op.bulk_insert(instance, [{"key": 1, "id": uuid.uuid4()}])


def downgrade() -> None:
    op.drop_table("instance")
