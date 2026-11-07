"""The devices a person receives notifications on (web push)

Revision ID: 0069
Revises: 0068
Create Date: 2026-11-07 08:00:00.000000

A browser that subscribed to notifications (Tobi, 06.11.2026): its address at its push service
(unique: whoever signed in there last), its two keys, a name, the language its notifications
speak, when a message last reached the push service and the failures since. The table is new;
the downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0069"
down_revision: str | None = "0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), nullable=False),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("last_success_at", types.UtcDateTime(), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(op.f("ix_push_devices_user_id"), "push_devices", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_push_devices_user_id"), table_name="push_devices")
    op.drop_table("push_devices")
