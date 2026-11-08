"""Fewer kinds at contacts: only customer, contract and personnel numbers and e-mail domains

Revision ID: 0072
Revises: 0071
Create Date: 2026-11-08 16:00:00.000000

Issue #215 (Tobi, 08.11.2026): a kind that only points to the contact is no identifier of it;
the language model and the classifier recognise the contact anyway. A contact keeps its
customer, contract and personnel numbers and the e-mail domains a person entered (for its logo
and as holder). Its identifiers of the other kinds go, entered, learned and rejected alike:
IBAN, VAT ID, commercial register number, tax number, creditor ID, licence plate, meter
number, mandate reference; so do learned e-mail domains (training learns none any more). They
stay facts of the documents; a person's IBAN in a profile stays. VAT IDs and creditor IDs have
no holder any more: the facts of these kinds lose theirs.

The downgrade changes nothing: the dropped identifiers are gone.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072"
down_revision: str | None = "0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DROPPED = (
    "iban",
    "vat_id",
    "commercial_register",
    "tax_number",
    "creditor_id",
    "license_plate",
    "meter_number",
    "mandate_reference",
)
WITHOUT_HOLDER = ("vat_id", "creditor_id")


def upgrade() -> None:
    identifiers = sa.table("contact_identifiers", sa.column("kind"), sa.column("source"))
    op.execute(identifiers.delete().where(identifiers.c.kind.in_(DROPPED)))
    op.execute(
        identifiers.delete().where(
            (identifiers.c.kind == "email_domain") & (identifiers.c.source == "learned")
        )
    )
    facts = sa.table(
        "document_facts",
        sa.column("kind"),
        sa.column("holder"),
        sa.column("holder_name"),
        sa.column("holder_source"),
    )
    op.execute(
        facts.update()
        .where(facts.c.kind.in_(WITHOUT_HOLDER))
        .values(holder=None, holder_name=None, holder_source=None)
    )


def downgrade() -> None:
    pass
