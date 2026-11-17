"""SEPA mandate reference (Mandatsreferenz): a fact of the document, since #215 no contact's
identifier; points to the direct debit mandate."""

from lekto.core.domain.identifiers.base import (
    IdentifierKind,
    LabelledNumber,
)


class MandateReference(LabelledNumber):
    kind = IdentifierKind.MANDATE_REFERENCE
    for_contacts = True
    names_user = True
    longest = 35
    labels = r"mandats[-\s]*(?:referenz|ref)|mandate[-\s]*(?:reference|ref)"
