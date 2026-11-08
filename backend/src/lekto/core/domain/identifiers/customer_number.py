"""Customer number: a contact's, which may name the user it belongs to (Anna's customer
account); found after its label. Until #145 also the contract, policy and membership numbers,
which have kinds of their own now; a contact's customer number still matches them
(`identifier.matches`)."""

import re
from collections.abc import Iterator

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identifiers.base import (
    MASKED,
    SEPARATORS,
    VALUE,
    Candidate,
    IdentifierKind,
    IdentifierType,
)
from lekto.core.domain.reasons import ReasonCode, because

_FORM = re.compile(r"(?=[A-Z0-9]*\d)[A-Z0-9]{4,30}")
_ACCOUNT = re.compile(r"account")
_BANK = re.compile(r"(?<![a-z])(?:routing|swift|iban|bic|bank)(?![a-z])")
_NEAR = 60
"""Characters around an "account number" in which a bank's word makes it a bank account."""
_LETTERS_AFTER_SLASH = re.compile(r"/[a-zäöü]")
_LABEL = re.compile(
    r"(?:kunden[-\s]*(?:nummer|nr|konto)|kd[-.\s]*nr|kundennr"
    r"|customer[-\s]*(?:no|number|id)|account[-\s]*(?:no|number))" + VALUE
)


class CustomerNumber(IdentifierType):
    kind = IdentifierKind.CUSTOMER_NUMBER
    for_contacts = True
    names_user = True

    def normalise(self, raw: str) -> str:
        """Without separators, in upper case: 4 to 30 letters and digits, one a digit; none
        where a character is hidden (`XXXXXX123`)."""
        value = SEPARATORS.sub("", raw.strip()).upper()
        if not _FORM.fullmatch(value) or MASKED.search(raw.upper()):
            raise ValidationError(because(ReasonCode.NOT_CUSTOMER_NUMBER, value=raw))
        return value

    def find(self, text: str) -> Iterator[Candidate]:
        """After its label; not an "account number" with a bank's word near it (routing,
        SWIFT, IBAN, BIC: a bank account), and up to a slash before letters (the invoice
        number a booking adds: `4711000815/RG 12345678`)."""
        for match in _LABEL.finditer(text):
            near = text[max(0, match.start() - _NEAR) : match.end() + _NEAR]
            if _ACCOUNT.match(match.group()) and _BANK.search(near):
                continue
            raw, (start, end) = match.group(1), match.span(1)
            slash = _LETTERS_AFTER_SLASH.search(raw)
            if slash is not None:
                raw, end = raw[: slash.start()], start + slash.start()
            yield Candidate(self.kind, raw, (start, end))
