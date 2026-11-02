"""A tax number names no user

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-02 12:00:00.000000

A company's tax number stands on all its letters: it tells which contact a document comes from,
never whose it is (Tobi, 02.11.2026). Training had given a learned one to the user whose
documents it stood in, and a user could enter one as theirs. A learned one keeps its row and
names nobody; it stays visible to the members of the spaces it was learned in. One a user
entered as theirs is dropped: naming nobody, everyone would see it.

The downgrade changes nothing: whom a number named is gone, and the code before reads one that
names nobody as it is.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    identifiers = sa.table(
        "contact_identifiers", sa.column("kind"), sa.column("source"), sa.column("user_id")
    )
    named = (identifiers.c.kind == "tax_number") & identifiers.c.user_id.is_not(None)
    op.execute(identifiers.delete().where(named & (identifiers.c.source == "manual")))
    op.execute(identifiers.update().where(named).values(user_id=None))


def downgrade() -> None:
    pass
