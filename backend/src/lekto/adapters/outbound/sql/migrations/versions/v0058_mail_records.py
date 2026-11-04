"""The mails fetched and where documents came from

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-04 18:00:00.000000

`mail_records`: every mail Lekto fetched from a mailbox (folder, UIDVALIDITY and UID, the
Message-ID, what became of it), so it is not fetched again; they go with their mailbox.
`mail_origins`: the mail, mailbox and rule a document came from; they go with the document and
stay when the mailbox goes. Nobody has any after the update. The downgrade drops both.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("folder", sa.Text(), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger(), nullable=False),
        sa.Column("uid", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=True),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("sent_at", types.UtcDateTime(), nullable=True),
        sa.Column("arrived_at", types.UtcDateTime(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("reason", types.json_type(), nullable=True),
        sa.Column("rule", sa.Text(), nullable=True),
        sa.Column("documents", sa.Integer(), nullable=False),
        sa.Column("fetched_at", types.UtcDateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["mailbox_id"],
            ["mailboxes.id"],
            name=op.f("fk_mail_records_mailbox_id_mailboxes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_records")),
        sa.UniqueConstraint(
            "mailbox_id",
            "folder",
            "uidvalidity",
            "uid",
            name=op.f("uq_mail_records_mailbox_id_folder_uidvalidity_uid"),
        ),
    )
    op.create_index(op.f("ix_mail_records_message_id"), "mail_records", ["message_id"])
    op.create_index(
        op.f("ix_mail_records_mailbox_id_fetched_at"), "mail_records", ["mailbox_id", "fetched_at"]
    )
    op.create_table(
        "mail_origins",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("mailbox", sa.Text(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("letter", sa.Integer(), nullable=False),
        sa.Column("outer", sa.Boolean(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=True),
        sa.Column("sender", types.json_type(), nullable=False),
        sa.Column("recipients", types.json_type(), nullable=False),
        sa.Column("copies", types.json_type(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("sent_at", types.UtcDateTime(), nullable=True),
        sa.Column("arrived_at", types.UtcDateTime(), nullable=False),
        sa.Column("forwarded_by", types.json_type(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("related", types.json_type(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_mail_origins_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id", name=op.f("pk_mail_origins")),
    )
    op.create_index(op.f("ix_mail_origins_record_id"), "mail_origins", ["record_id"])


def downgrade() -> None:
    op.drop_table("mail_origins")
    op.drop_table("mail_records")
