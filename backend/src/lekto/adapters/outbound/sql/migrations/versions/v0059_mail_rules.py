"""Mail rules, and the type a mail's text gets

Revision ID: 0059
Revises: 0058
Create Date: 2026-11-04 21:00:00.000000

`mail_rules`: what a mailbox's mails bring in (conditions as JSON, the person, space and type
without foreign keys: a rule whose one is gone is paused); they go with their mailbox. A
mail's origin keeps the type its text gets (`mail_origins.body_type_id`), which the rules node
sets. Nobody has a rule after the update. The downgrade drops both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mail_origins", sa.Column("body_type_id", sa.Uuid(), nullable=True))
    op.create_table(
        "mail_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("any", sa.Boolean(), nullable=False),
        sa.Column("conditions", types.json_type(), nullable=False),
        sa.Column("parts", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("space_id", sa.Uuid(), nullable=True),
        sa.Column("text_type_id", sa.Uuid(), nullable=True),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("move_to", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_reason", types.json_type(), nullable=True),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", types.UtcDateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mailbox_id"],
            ["mailboxes.id"],
            name=op.f("fk_mail_rules_mailbox_id_mailboxes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_rules")),
    )
    op.create_index(op.f("ix_mail_rules_mailbox_id"), "mail_rules", ["mailbox_id"])


def downgrade() -> None:
    op.drop_table("mail_rules")
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("mail_origins", "body_type_id")
