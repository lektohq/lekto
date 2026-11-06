"""Mail records keep which rule took the mail, when, and its steps on the server

Revision ID: 0068
Revises: 0067
Create Date: 2026-11-06 10:00:00.000000

A mail no rule took is taken later by a rule switched on afterwards (Tobi, 06.11.2026), and a
mailbox's page shows what became of each mail. `mail_records` keeps the rule by id
(`rule_id`; `rule` stays its name then), when a rule or the fallback decided (`decided_at`, later
than `fetched_at` for a mail taken afterwards), the steps on the server with why one failed
(`steps`, JSON; NULL: none) and when a fetch found the mail gone from its folder while no rule had
taken it (`gone_at`). The records before know none of it. The columns have no keys, so SQLite adds
them in place; the downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0068"
down_revision: str | None = "0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mail_records", sa.Column("rule_id", sa.Uuid(), nullable=True))
    op.add_column("mail_records", sa.Column("decided_at", types.UtcDateTime(), nullable=True))
    op.add_column("mail_records", sa.Column("steps", types.json_type(), nullable=True))
    op.add_column("mail_records", sa.Column("gone_at", types.UtcDateTime(), nullable=True))


def downgrade() -> None:
    # Not batch operations: on SQLite, they would copy the table.
    for name in ("gone_at", "steps", "decided_at", "rule_id"):
        op.drop_column("mail_records", name)
