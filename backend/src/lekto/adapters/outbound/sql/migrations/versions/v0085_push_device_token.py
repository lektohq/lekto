"""A push device knows the API token it was registered through

Revision ID: 0085
Revises: 0084
Create Date: 2026-11-23 18:00:00.000000

Revoking an API token deletes the push devices registered through it, as its webhooks (Tobi,
23.11.2026, XA-K04): titles and events no longer reach a device of a script once its token is
revoked. Devices registered before know no token.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0085"
down_revision: str | None = "0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("push_devices") as batch:
        batch.add_column(sa.Column("api_token_id", sa.Uuid(), nullable=True))
        batch.create_index(op.f("ix_push_devices_api_token_id"), ["api_token_id"])
        batch.create_foreign_key(
            op.f("fk_push_devices_api_token_id_api_tokens"),
            "api_tokens",
            ["api_token_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("push_devices") as batch:
        batch.drop_constraint(op.f("fk_push_devices_api_token_id_api_tokens"), type_="foreignkey")
        batch.drop_index(op.f("ix_push_devices_api_token_id"))
        batch.drop_column("api_token_id")
