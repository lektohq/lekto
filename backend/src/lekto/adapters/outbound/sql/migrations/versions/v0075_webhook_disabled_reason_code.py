"""Why a webhook was switched off, with its code

Revision ID: 0075
Revises: 0074
Create Date: 2026-11-09 12:00:00.000000

A webhook Lekto switched off after repeated failed deliveries kept the word `failing` in
`webhooks.disabled_reason`; now it keeps a reason with its code, as mail rules do
(`{"code": "webhook_failing", "params": {}}`, review 0.12.2, C-07). The text column becomes a
JSON column of the same name: the reason is written into a new column, the old one dropped and
the new one renamed (a plain `ALTER TABLE`, which SQLite and PostgreSQL both know). Any other
value never was written; it becomes none. The downgrade writes `failing` back.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FAILING = {"code": "webhook_failing", "params": {}}


def _move(
    old_type: sa.types.TypeEngine[Any], new_type: sa.types.TypeEngine[Any], value: object
) -> None:
    """Every webhook switched off keeps `value` in a column of `new_type` by the same name."""
    op.add_column("webhooks", sa.Column("disabled_reason_new", new_type, nullable=True))
    webhooks = sa.table(
        "webhooks",
        sa.column("disabled_reason", old_type),
        sa.column("disabled_reason_new", new_type),
    )
    op.execute(
        webhooks.update()
        .where(webhooks.c.disabled_reason.is_not(None))
        .values(disabled_reason_new=value)
    )
    op.drop_column("webhooks", "disabled_reason")
    op.execute("ALTER TABLE webhooks RENAME COLUMN disabled_reason_new TO disabled_reason")


def upgrade() -> None:
    _move(sa.Text(), types.json_type(), FAILING)


def downgrade() -> None:
    _move(types.json_type(), sa.Text(), "failing")
