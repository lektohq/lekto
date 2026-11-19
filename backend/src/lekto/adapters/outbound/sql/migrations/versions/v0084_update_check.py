"""The last look at Lekto's releases

Revision ID: 0084
Revises: 0083
Create Date: 2026-11-19 22:00:00.000000

The worker asks for Lekto's releases every hour (Tobi, 19.11.2026,
`.knowledge/open/update-notifier-fas.md`) and keeps, in the row of the instance, when it asked
and the newest release that was news then.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0084"
down_revision: str | None = "0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("update_checked_at", "latest_version", "latest_published_at", "latest_url")


def upgrade() -> None:
    with op.batch_alter_table("instance") as batch:
        batch.add_column(sa.Column("update_checked_at", types.UtcDateTime(), nullable=True))
        batch.add_column(sa.Column("latest_version", sa.Text(), nullable=True))
        batch.add_column(sa.Column("latest_published_at", types.UtcDateTime(), nullable=True))
        batch.add_column(sa.Column("latest_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instance") as batch:
        for column in reversed(_COLUMNS):
            batch.drop_column(column)
