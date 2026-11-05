"""What a mail is marked with: To and Cc apart, its importance, its keywords and flag

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-05 16:00:00.000000

Mail rules and document rules look at To and Cc apart, the importance and the marks on the
server (Tobi, 05.11.2026; `mail_traits`):

- `mail_records`: `to_texts` and `cc_texts` (empty for the mails fetched before, whose
  `recipients` hold both), `importance`, `keywords` and `flag` (NULL: not known).
- `mail_origins`: `importance`, `keywords` and `flag`, likewise NULL for the documents taken
  before.
- `mailboxes`: `keywords` its folders knew at the last fetch (none yet) and `own_keywords`,
  whether the server stores Lekto's own (NULL: not known before the next fetch).

The columns have no keys, so SQLite adds them in place; the downgrade drops them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _marks() -> list[sa.Column[object]]:
    return [
        sa.Column("importance", sa.Text(), nullable=True),
        sa.Column("keywords", types.json_type(), nullable=True),
        sa.Column("flag", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    for name in ("to_texts", "cc_texts"):
        op.add_column(
            "mail_records",
            sa.Column(name, types.json_type(), nullable=False, server_default="[]"),
        )
    for table in ("mail_records", "mail_origins"):
        for column in _marks():
            op.add_column(table, column)
    op.add_column(
        "mailboxes",
        sa.Column("keywords", types.json_type(), nullable=False, server_default="[]"),
    )
    op.add_column("mailboxes", sa.Column("own_keywords", sa.Boolean(), nullable=True))


def downgrade() -> None:
    # Not batch operations: on SQLite, they would copy the tables.
    op.drop_column("mailboxes", "own_keywords")
    op.drop_column("mailboxes", "keywords")
    for table in ("mail_origins", "mail_records"):
        for name in ("flag", "keywords", "importance"):
            op.drop_column(table, name)
    for name in ("cc_texts", "to_texts"):
        op.drop_column("mail_records", name)
