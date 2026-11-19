"""A webhook knows the API token it was created through

Revision ID: 0082
Revises: 0081
Create Date: 2026-11-19 18:00:00.000000

Revoking an API token deletes the webhooks created through it (Tobi, 19.11.2026,
`.knowledge/plans/token-rights.md`), so that a service such as Home Assistant leaves no webhook
behind that nobody removes. Webhooks created before know no token.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: str | None = "0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("webhooks") as batch:
        batch.add_column(sa.Column("api_token_id", sa.Uuid(), nullable=True))
        batch.create_index(op.f("ix_webhooks_api_token_id"), ["api_token_id"])
        batch.create_foreign_key(
            op.f("fk_webhooks_api_token_id_api_tokens"),
            "api_tokens",
            ["api_token_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("webhooks") as batch:
        batch.drop_constraint(op.f("fk_webhooks_api_token_id_api_tokens"), type_="foreignkey")
        batch.drop_index(op.f("ix_webhooks_api_token_id"))
        batch.drop_column("api_token_id")
