"""Meter number (Zählernummer, Zählpunkt): a fact of the document, since #215 no contact's
identifier; points to the meter a utility's bills refer to."""

from lekto.core.domain.identifiers.base import (
    COMPOUND,
    IdentifierKind,
    LabelledNumber,
)


class MeterNumber(LabelledNumber):
    kind = IdentifierKind.METER_NUMBER
    for_contacts = True
    names_user = True
    # Not an OBIS code (`1.8.0`, the register a reading is of).
    shortest = 6
    fewest_digits = 4
    longest = 40
    compounds = COMPOUND
    labels = (
        r"zähler[-\s]*(?:nummer|nr)|zählpunkt(?:[-\s]*(?:nummer|bezeichnung))?"
        r"|meter[-\s]*(?:no|number)"
    )
