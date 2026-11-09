"""Why a webhook delivery was not sent, with its code

Revision ID: 0076
Revises: 0075
Create Date: 2026-11-09 14:00:00.000000

A delivery Lekto did not send (the webhook switched off, the owner inactive, the document out of
reach, the webhook deleted, the secret unusable) keeps why with its code
(`webhook_deliveries.reason`, review 0.12.2, C-07) beside the English text in `error`, so that
clients can give it in their language. Deliveries before have none: their text stays.

The column has no keys, so SQLite adds it in place. The downgrade drops it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0076"
down_revision: str | None = "0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("webhook_deliveries", sa.Column("reason", types.json_type(), nullable=True))


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("webhook_deliveries", "reason")
