"""Contract number: a contact's, which may name the user it belongs to; points to the contract a
series of documents refers to. Since #215 one kind for every running contract: a contract
(Vertragsnummer, Vertragskonto), an insurance policy (Versicherungsschein-, Policennummer), a
membership (Mitgliedsnummer) and a loan (Darlehens-, Kreditnummer). Not a person's insurance
number: "Renten-" and "Krankenversicherungsnummer" are no label of it."""

from collections.abc import Iterator

from lekto.core.domain.identifiers.base import (
    COMPOUND,
    Candidate,
    IdentifierKind,
    LabelledNumber,
    after_labels,
    labelled,
)

_PERSONS = "sozial|renten|kranken"
_INSURANCE_DIGITS = 6
"""Digits a number after an insurance label has at least: not the postcode on the line after
the label, nor letters of an address."""


class ContractNumber(LabelledNumber):
    kind = IdentifierKind.CONTRACT_NUMBER
    for_contacts = True
    at_contacts = True
    learned = True
    names_user = True
    fewest_digits = 4  # not a short code of a form ("332")
    compounds = COMPOUND
    labels = (
        r"vertrags[-\s]*(?:nummer|nr|konto(?:[-\s]*(?:nummer|nr))?)|contract[-\s]*(?:no|number|id)"
        r"|mitglieds[-\s]*(?:nummer|nr)|member(?:ship)?[-\s]*(?:no|number|id)"
        r"|darlehens[-\s]*(?:nummer|nr|konto(?:[-\s]*(?:nummer|nr))?)"
        r"|kredit[-\s]*(?:nummer|nr)|loan[-\s]*(?:no|number)"
    )
    # Not a person's number ("Sozialversicherungsnummer", "Renten-", "Krankenversicherungsnummer").
    insurance_compounds = rf"(?!(?:{_PERSONS})-?versicherungs){COMPOUND}"
    insurance_labels = (
        r"(?<!sozial[- ])(?<!renten[- ])(?<!kranken[- ])"
        r"versicherungs[-\s]*(?:schein[-\s]*)?(?:nummer|nr)|police?n?[-\s]*(?:nummer|nr)"
        r"|policy[-\s]*(?:no|number)"
    )

    def __init__(self) -> None:
        super().__init__()
        self._insurance = labelled(
            self.insurance_labels, self.value, compounds=self.insurance_compounds
        )

    def find(self, text: str) -> Iterator[Candidate]:
        """After a contract's, a membership's or a loan's label; after an insurance policy's
        with at least six digits."""
        yield from super().find(text)
        for candidate in after_labels(self.kind, self._insurance, text):
            if sum(char.isdigit() for char in candidate.raw) >= _INSURANCE_DIGITS:
                yield candidate
