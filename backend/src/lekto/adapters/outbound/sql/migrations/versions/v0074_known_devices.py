"""Known devices: browsers that signed in with the password count failed sign-ins apart

Revision ID: 0074
Revises: 0073
Create Date: 2026-11-08 18:00:00.000000

A browser that signed in with the password keeps a device token (OWASP's device cookies; Tobi,
08.11.2026); only its SHA-256 hash is stored, with the user and until when the device stays
known (a year after its last sign-in). Its failed sign-ins count under the device, not the
account, so guesses from elsewhere that block an account do not lock its owner out. The table
is new; the downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0074"
down_revision: str | None = "0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "known_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("expires_at", types.UtcDateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_known_devices_user_id"), "known_devices", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_known_devices_expires_at"), "known_devices", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_known_devices_expires_at"), table_name="known_devices")
    op.drop_index(op.f("ix_known_devices_user_id"), table_name="known_devices")
    op.drop_table("known_devices")
