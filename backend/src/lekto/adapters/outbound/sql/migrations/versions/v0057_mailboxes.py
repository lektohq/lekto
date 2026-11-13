"""Mailboxes

Revision ID: 0057
Revises: 0056
Create Date: 2026-11-04 12:00:00.000000

The mailboxes Lekto fetches from (`.idea/decisions/2026-11-04-mail.md`): server, account, the
password encrypted, folders, interval, from when on, the fallback, the type of a mail's text and
the status of the fetches. Names unique regardless of case. A document type or a person a
mailbox names cannot be deleted. Nobody has one after the update. The downgrade drops the table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mailboxes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("security", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password", sa.LargeBinary(), nullable=False),
        sa.Column("folders", types.json_type(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("start", sa.Text(), nullable=False),
        sa.Column("since", sa.Date(), nullable=True),
        sa.Column("fallback", sa.Text(), nullable=False),
        sa.Column("fallback_user_id", sa.Uuid(), nullable=True),
        sa.Column("body_type_id", sa.Uuid(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_attempt_at", types.UtcDateTime(), nullable=True),
        sa.Column("last_success_at", types.UtcDateTime(), nullable=True),
        sa.Column("error", types.json_type(), nullable=True),
        sa.Column("mails", sa.Integer(), nullable=False),
        sa.Column("documents", sa.Integer(), nullable=False),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", types.UtcDateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fallback_user_id"],
            ["users.id"],
            name=op.f("fk_mailboxes_fallback_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["body_type_id"],
            ["document_types.id"],
            name=op.f("fk_mailboxes_body_type_id_document_types"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mailboxes")),
        sa.UniqueConstraint("name_key", name=op.f("uq_mailboxes_name_key")),
    )


def downgrade() -> None:
    op.drop_table("mailboxes")
