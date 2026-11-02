"""A company's tax number (Steuernummer), on all its letters: it tells which contact a document
comes from, never whose it is, so it names no user (Tobi, 02.11.2026). Found after its label
("Steuernummer", "St.-Nr."), compared as its digits (`123/456/78901` is `12345678901`). A
person's tax ID written after "Steuernummer" is none (`tax_id_valid`)."""

import re

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identifiers.base import IdentifierKind, LabelledNumber
from lekto.core.domain.identifiers.tax_id import tax_id_valid
from lekto.core.domain.reasons import ReasonCode, because

_FORM = re.compile(r"\d{10,13}")


class TaxNumber(LabelledNumber):
    kind = IdentifierKind.TAX_NUMBER
    for_contacts = True
    labels = r"steuer[-\s]*(?:nummer|nr)|st[-.\s]*nr|tax[-\s]*number"

    def normalise(self, raw: str) -> str:
        """Its digits: 10 to 13 of them, and no tax ID."""
        value = re.sub(r"[\s./-]+", "", raw.strip())
        if not _FORM.fullmatch(value) or tax_id_valid(value):
            raise ValidationError(because(ReasonCode.NOT_OF_KIND, kind=self.kind.value, value=raw))
        return value
