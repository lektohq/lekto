"""Versions of a document's original

Revision ID: 0077
Revises: 0076
Create Date: 2026-11-10 18:00:00.000000

A document has versions of its original (Tobi, 10.11.2026;
`.idea/decisions/2026-11-10-versions.md`): a new one comes in when a person replaces the file or
edits the pages; none is overwritten. `document_versions` keeps them all, gone with their document;
the document keeps naming its current one (`documents.sha256`, `original_filename`, `media_type`).
Every existing document gets its first version: its original as it came in, by who uploaded it.
Every file exists once per installation, the earlier versions' too (a unique index).
`documents.processing_new_version` tells a run that reads a new version (`Processing.new_version`);
none does yet.

The downgrade drops the table and the column: a document keeps its current original, the
earlier ones are forgotten (their files stay in the store until removed by hand).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0077"
down_revision: str | None = "0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "processing_new_version", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.create_table(
        "document_versions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("detail", types.json_type(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_versions_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_document_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("document_id", "number", name=op.f("pk_document_versions")),
    )
    op.create_index(
        op.f("ix_document_versions_sha256"), "document_versions", ["sha256"], unique=True
    )
    op.execute(
        "INSERT INTO document_versions "
        "(document_id, number, sha256, original_filename, media_type, kind, created_at, "
        "created_by, detail) "
        "SELECT id, 1, sha256, original_filename, media_type, 'received', created_at, "
        "uploaded_by, '{}' FROM documents"
    )


def downgrade() -> None:
    # Not a batch operation: on SQLite, it would copy the table.
    op.drop_column("documents", "processing_new_version")
    op.drop_index(op.f("ix_document_versions_sha256"), table_name="document_versions")
    op.drop_table("document_versions")
