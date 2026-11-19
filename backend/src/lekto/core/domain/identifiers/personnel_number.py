"""Personnel number: an employee's at the employer (a contact's, which may name the user it
belongs to); found after its label ("Personalnummer", "Pers.-Nr.", "Mitarbeiternummer",
"Employee ID"), compared without leading zeros (`00012345` is `12345`)."""

import re
from collections.abc import Iterator

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identifiers.base import (
    SEPARATORS,
    VALUE,
    WRITTEN_SEPARATORS,
    Candidate,
    IdentifierKind,
    IdentifierType,
    after_label,
)
from lekto.core.domain.reasons import ReasonCode, because

MIN_LENGTH = 3
MAX_LENGTH = 30
"""The letters and digits a personnel number has at least and at most, as written."""
_FORM = re.compile(rf"(?=[A-Z0-9]*\d)[A-Z0-9]{{{MIN_LENGTH},{MAX_LENGTH}}}")
_LABEL = re.compile(
    r"(?<![a-z])(?:personal[-\s]*(?:nummer|nr)|pers[-.\s]*nr|mitarbeiter[-\s]*(?:nummer|nr)"
    r"|employee[-\s]*(?:no|number|id)|personnel[-\s]*(?:no|number))" + VALUE
)


class PersonnelNumber(IdentifierType):
    kind = IdentifierKind.PERSONNEL_NUMBER
    for_contacts = True
    at_contacts = True
    learned = True
    names_user = True

    def normalise(self, raw: str) -> str:
        """Without separators and leading zeros, in upper case: `MIN_LENGTH` to `MAX_LENGTH`
        letters and digits as written, one a digit."""
        written = SEPARATORS.sub("", raw.strip()).upper()
        value = written.lstrip("0")
        if not _FORM.fullmatch(written) or not value:
            raise ValidationError(
                because(ReasonCode.NOT_PERSONNEL_NUMBER, value=raw, min=MIN_LENGTH, max=MAX_LENGTH)
            )
        return value

    def find(self, text: str) -> Iterator[Candidate]:
        return after_label(self.kind, _LABEL, text)

    def written(self, value: str) -> str:
        """Also with leading zeros."""
        pattern = WRITTEN_SEPARATORS.join(re.escape(char) for char in value)
        return rf"(?<![A-Za-z0-9])(?:0{WRITTEN_SEPARATORS})*{pattern}(?![A-Za-z0-9])"
