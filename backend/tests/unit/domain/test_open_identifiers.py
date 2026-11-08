"""The open identifiers: learned at a contact, or standing in confirmed documents at no contact."""

from dataclasses import replace
from datetime import date

from lekto.core.domain.document_facts import (
    DocumentFact,
    FactOrigin,
    FactRole,
    Holder,
    HolderKind,
    HolderSource,
    role_of,
)
from lekto.core.domain.identifiers import Identifier, IdentifierKind, IdentifierSource
from lekto.core.domain.ids import ContactId, DocumentId, UserId, new_id
from lekto.core.domain.master_data import Contact
from lekto.core.domain.open_identifiers import (
    OpenSource,
    Recommendation,
    Sighting,
    excerpt,
    open_identifiers,
)
from lekto.core.domain.profiles import Person
from lekto.core.domain.reasons import ReasonCode
from tests.builders import NOW

IBAN = (IdentifierKind.IBAN, "DE02120300000000202051")
VAT = (IdentifierKind.VAT_ID, "DE312456789")
CUSTOMER = (IdentifierKind.CUSTOMER_NUMBER, "20047718")
CONTRACT = (IdentifierKind.CONTRACT_NUMBER, "20047718")
OTHER = (IdentifierKind.CUSTOMER_NUMBER, "55667788")
DOMAIN = (IdentifierKind.EMAIL_DOMAIN, "stadtwerke.example")
INVOICE = (IdentifierKind.INVOICE_NUMBER, "R-4711")


def fact(
    key: tuple[IdentifierKind, str], written: str | None = None, holder: Holder | None = None
) -> DocumentFact:
    kind, value = key
    return DocumentFact(
        kind=kind,
        value=value,
        role=role_of(kind),
        origins=frozenset({FactOrigin.PATTERN}),
        written=written,
        position=0,
        holder=holder,
    )


def seen(
    contact: ContactId,
    key: tuple[IdentifierKind, str],
    day: int,
    written: str | None = None,
    holder: Holder | None = None,
    owner: UserId | None = None,
) -> Sighting:
    return Sighting(
        DocumentId(new_id()), contact, date(2026, 10, day), fact(key, written, holder), owner
    )


def test_a_learned_one_is_open_with_the_documents_that_show_it() -> None:
    utility = Contact.create(name="Stadtwerke", now=NOW)
    utility.set_learned([Identifier(*CUSTOMER, IdentifierSource.LEARNED)])
    sightings = [seen(utility.id, CUSTOMER, 1), seen(utility.id, CONTRACT, 9, "2004 7718")]
    (item,) = open_identifiers([utility], sightings)
    # A customer number stands for the contract number of its value.
    assert (item.key, item.source, item.contacts) == (CUSTOMER, OpenSource.LEARNED, (utility.id,))
    assert [each.dated.day for each in item.seen] == [9, 1]
    assert (item.written, item.last) == ("2004 7718", date(2026, 10, 9))


def test_a_domain_that_fits_its_contact_s_name_is_suggested_for_it() -> None:
    """Since #215 a contact's kind at no contact is no longer open (unknown): only a domain whose
    name fits the contact of its documents, while that contact has none entered (#215)."""
    utility, bank = (Contact.create(name=name, now=NOW) for name in ("Stadtwerke Nord", "Bank"))
    site = (IdentifierKind.EMAIL_DOMAIN, "stadtwerke-nord.example")
    portal = (IdentifierKind.EMAIL_DOMAIN, "kundenportal.example")
    sightings = [
        seen(utility.id, site, 4),
        seen(utility.id, site, 5),
        seen(bank.id, site, 3),  # the bank's name does not fit it
        seen(utility.id, portal, 5),  # nor does the utility's this one
        seen(utility.id, OTHER, 5),  # a customer number at no contact: not open
        seen(utility.id, INVOICE, 5),
        seen(utility.id, VAT, 5),
    ]
    (item,) = open_identifiers([utility, bank], sightings)
    assert (item.key, item.source, item.contacts) == (site, OpenSource.SUGGESTED, (utility.id,))
    assert len(item.seen) == 2  # its contact's documents
    assert advice(item) == (Recommendation.CONFIRM, ReasonCode.RECOMMEND_CONFIRM_NAMED)
    # A contact with a domain entered gets none suggested.
    utility.set_identifiers([Identifier(IdentifierKind.EMAIL_DOMAIN, "nord.example")])
    assert open_identifiers([utility, bank], sightings) == []


def test_an_iban_or_a_vat_id_is_no_contact_s() -> None:
    """Since #215 a contact carries neither: they are never open at one, nor suggested for one
    (an IBAN is suggested for a person's profile only)."""
    utility, bank = (Contact.create(name=name, now=NOW) for name in ("Stadtwerke", "Bank"))
    payee = Holder(HolderKind.THIRD_PARTY, HolderSource.RULE, "Stadtwerke")
    own = Holder(HolderKind.SENDER, HolderSource.RULE)
    sightings = [
        seen(bank.id, IBAN, 3, holder=payee),
        seen(bank.id, IBAN, 4, holder=payee),
        seen(utility.id, IBAN, 5, holder=own),
        seen(utility.id, IBAN, 6, holder=own),
        seen(utility.id, VAT, 5),
        seen(utility.id, VAT, 6),
    ]
    assert open_identifiers([utility, bank], sightings) == []


def test_a_recipient_s_iban_is_suggested_for_their_profile() -> None:
    """Named, for the person it names; unnamed, for the user whose personal space holds the
    document; not one they declined, nor where the documents point to two people."""
    bank = Contact.create(name="Bank", now=NOW)
    max_, lisa = UserId(new_id()), UserId(new_id())
    persons = [Person(max_, "Max Nord"), Person(lisa, "Lisa Nord", aliases=("Lisa Süd",))]
    named = Holder(HolderKind.RECIPIENT, HolderSource.RULE, "Max Nord")
    (item,) = open_identifiers([bank], [seen(bank.id, IBAN, 3, holder=named)], persons=persons)
    assert (item.source, item.contacts, item.person) == (OpenSource.SUGGESTED, (), max_)
    yours = Holder(HolderKind.RECIPIENT, HolderSource.RULE)
    (item,) = open_identifiers(
        [bank], [seen(bank.id, IBAN, 3, holder=yours, owner=lisa)], persons=persons
    )
    assert item.person == lisa
    both = [seen(bank.id, IBAN, 3, holder=named), seen(bank.id, IBAN, 4, holder=yours, owner=lisa)]
    assert open_identifiers([bank], both, persons=persons) == []
    assert (
        open_identifiers(
            [bank], [seen(bank.id, IBAN, 3, holder=named)], persons=persons, declined={max_: [IBAN]}
        )
        == []
    )
    # In a profile already: nothing to suggest.
    assert open_identifiers([bank], [seen(bank.id, IBAN, 3, holder=named)], [IBAN], persons) == []


def test_a_recipient_s_domain_or_customer_number_is_suggested_for_no_profile() -> None:
    """A person has no e-mail domain or customer number among their numbers: nothing to
    suggest."""
    bank = Contact.create(name="Bank", now=NOW)
    max_ = UserId(new_id())
    named = Holder(HolderKind.RECIPIENT, HolderSource.RULE, "Max Nord")
    domain = (IdentifierKind.EMAIL_DOMAIN, "nord-familie.example")
    sightings = [seen(bank.id, domain, 3, holder=named), seen(bank.id, OTHER, 4, holder=named)]
    assert open_identifiers([bank], sightings, persons=[Person(max_, "Max Nord")]) == []


def test_what_a_contact_or_a_person_has_is_not_open() -> None:
    utility = Contact.create(
        name="Stadtwerke",
        now=NOW,
        identifiers=[Identifier(*OTHER), Identifier(IdentifierKind.EMAIL_DOMAIN, "nord.example")],
    )
    utility.set_identifiers(
        [Identifier(*OTHER), Identifier(IdentifierKind.EMAIL_DOMAIN, "nord.example")],
        rejected=[Identifier(*CUSTOMER)],
    )
    sightings = [
        seen(utility.id, OTHER, 1),
        seen(utility.id, CONTRACT, 1),  # the rejected customer number's value
        seen(utility.id, (IdentifierKind.EMAIL_DOMAIN, "post.nord.example"), 1),  # subdomain
        seen(utility.id, IBAN, 1),  # the person's
        seen(utility.id, (IdentifierKind.EMAIL_DOMAIN, "gmail.com"), 1),
    ]
    assert open_identifiers([utility], sightings, personal=[IBAN]) == []


def test_the_most_documents_come_first_then_the_newest() -> None:
    utility = Contact.create(name="Stadtwerke", now=NOW)
    utility.set_learned(
        [
            Identifier(*CUSTOMER, IdentifierSource.LEARNED),
            Identifier(*OTHER, IdentifierSource.LEARNED),
        ]
    )
    sightings = [
        seen(utility.id, OTHER, 1),
        seen(utility.id, DOMAIN, 2),
        seen(utility.id, CUSTOMER, 3),
        seen(utility.id, CUSTOMER, 4),
    ]
    assert [item.key for item in open_identifiers([utility], sightings)] == [
        CUSTOMER,
        DOMAIN,
        OTHER,
    ]


def test_an_excerpt_shows_the_text_around_on_one_line() -> None:
    text = "Rechnung\n\nBitte überweise an\nIBAN DE02 1203 0000 0000 2020 51 bis Monatsende."
    start = text.index("DE02")
    cut = excerpt(text, start, len("DE02 1203 0000 0000 2020 51"))
    assert cut.before == "Rechnung Bitte überweise an IBAN "
    assert cut.match == "DE02 1203 0000 0000 2020 51"
    assert cut.after == " bis Monatsende."
    long = "Wort " * 60 + "DE312456789" + " Wort" * 60
    short = excerpt(long, long.index("DE3"), 11, reach=20)
    assert short.before.startswith("…") and short.after.endswith("…")
    assert short.match == "DE312456789"
    assert len(short.before) <= 21 and len(short.after) <= 21


# --- recommendations (Tobi, 28.10.2026) ---------------------------------------------------------

SENDER = Holder(HolderKind.SENDER, HolderSource.RULE)
THIRD = Holder(HolderKind.THIRD_PARTY, HolderSource.RULE)


def advice(item: object) -> tuple[Recommendation, ReasonCode] | None:
    recommended = item.recommended  # type: ignore[attr-defined]
    return None if recommended is None else (recommended.action, recommended.reason.code)


def test_one_in_two_documents_of_its_contact_alone_is_recommended_to_confirm() -> None:
    utility = Contact.create(name="Stadtwerke", now=NOW)
    utility.set_learned([Identifier(*CUSTOMER, IdentifierSource.LEARNED)])
    (one,) = open_identifiers([utility], [seen(utility.id, CUSTOMER, 1)])
    assert advice(one) is None  # one document tells too little
    (two,) = open_identifiers(
        [utility], [seen(utility.id, CUSTOMER, 1), seen(utility.id, CUSTOMER, 2)]
    )
    assert advice(two) == (Recommendation.CONFIRM, ReasonCode.RECOMMEND_CONFIRM)
    assert two.recommended is not None and two.recommended.reason.params == {
        "count": 2,
        "name": "Stadtwerke",
    }


def test_a_number_of_a_kind_with_a_holder_needs_its_contact_s_each_time() -> None:
    utility = Contact.create(name="Stadtwerke", now=NOW)
    utility.set_learned([Identifier(*DOMAIN, IdentifierSource.LEARNED)])  # learned before #215
    unread = [seen(utility.id, DOMAIN, 1), seen(utility.id, DOMAIN, 2)]  # read before holders
    assert advice(open_identifiers([utility], unread)[0]) is None
    own = [seen(utility.id, DOMAIN, 1, holder=SENDER), seen(utility.id, DOMAIN, 2, holder=SENDER)]
    assert advice(open_identifiers([utility], own)[0]) == (
        Recommendation.CONFIRM,
        ReasonCode.RECOMMEND_CONFIRM,
    )


def test_a_customer_number_is_its_contact_s_unless_a_booking_gives_it_another() -> None:
    utility = Contact.create(name="Stadtwerke", now=NOW)
    utility.set_learned([Identifier(*CUSTOMER, IdentifierSource.LEARNED)])
    # No holder told: the contact's, as before customer numbers had holders.
    unbooked = [seen(utility.id, CUSTOMER, 1), seen(utility.id, CUSTOMER, 2)]
    assert advice(open_identifiers([utility], unbooked)[0]) == (
        Recommendation.CONFIRM,
        ReasonCode.RECOMMEND_CONFIRM,
    )
    # One of its documents gives it another in a booking: learned there wrongly.
    booked = [seen(utility.id, CUSTOMER, 1), seen(utility.id, CUSTOMER, 2, holder=THIRD)]
    assert advice(open_identifiers([utility], booked)[0]) == (
        Recommendation.REJECT,
        ReasonCode.RECOMMEND_REJECT_FOREIGN,
    )


def test_a_learned_customer_number_of_the_bookings_is_recommended_to_reject() -> None:
    bank = Contact.create(name="Bank", now=NOW)
    bank.set_learned([Identifier(*CUSTOMER, IdentifierSource.LEARNED)])
    payees = [seen(bank.id, CUSTOMER, day, holder=THIRD) for day in (1, 2, 3)]
    (item,) = open_identifiers([bank], payees)
    assert advice(item) == (Recommendation.REJECT, ReasonCode.RECOMMEND_REJECT_FOREIGN)


def test_a_learned_one_someone_else_holds_is_recommended_to_reject() -> None:
    bank = Contact.create(name="Bank", now=NOW)
    bank.set_learned([Identifier(*DOMAIN, IdentifierSource.LEARNED)])
    payees = [seen(bank.id, DOMAIN, day, holder=THIRD) for day in (1, 2, 3)]
    (item,) = open_identifiers([bank], payees)
    assert advice(item) == (Recommendation.REJECT, ReasonCode.RECOMMEND_REJECT_FOREIGN)
    assert item.recommended is not None and item.recommended.reason.params["count"] == 3


def test_one_other_contacts_hold_as_theirs_is_recommended_to_reject() -> None:
    shop, other = (Contact.create(name=name, now=NOW) for name in ("Versandhaus", "Portal"))
    shop.set_learned([Identifier(*OTHER, IdentifierSource.LEARNED)])
    sightings = [seen(shop.id, OTHER, 1), seen(shop.id, OTHER, 2), seen(other.id, OTHER, 3)]
    (item,) = open_identifiers([shop, other], sightings)
    assert advice(item) == (Recommendation.REJECT, ReasonCode.RECOMMEND_REJECT_CONTACTS)


def test_a_payee_on_another_s_statement_does_not_count_against_it() -> None:
    utility, bank = (Contact.create(name=name, now=NOW) for name in ("Stadtwerke", "Bank"))
    utility.set_learned([Identifier(*OTHER, IdentifierSource.LEARNED)])
    sightings = [
        seen(utility.id, OTHER, 1),
        seen(utility.id, OTHER, 2),
        seen(bank.id, OTHER, 3, holder=THIRD),  # a booking on the bank's statement
    ]
    (item,) = open_identifiers([utility, bank], sightings)
    assert advice(item) == (Recommendation.CONFIRM, ReasonCode.RECOMMEND_CONFIRM)


def test_no_recommendation_for_a_reference_or_one_of_several_contacts() -> None:
    utility, bank = (Contact.create(name=name, now=NOW) for name in ("Stadtwerke", "Bank"))
    utility.set_learned([Identifier(*CUSTOMER, IdentifierSource.LEARNED)])
    referred = [
        seen(utility.id, CUSTOMER, 1),
        Sighting(
            DocumentId(new_id()),
            utility.id,
            date(2026, 10, 2),
            replace(fact(CUSTOMER), role=FactRole.REFERS),
        ),
    ]
    assert advice(open_identifiers([utility], referred)[0]) is None
    # One at no contact that two contacts' documents show is not open at all (#215).
    shared = [seen(utility.id, OTHER, 1), seen(utility.id, OTHER, 2), seen(bank.id, OTHER, 3)]
    assert [item.key for item in open_identifiers([utility, bank], shared)] == [CUSTOMER]


def test_a_suggestion_two_documents_name_is_recommended() -> None:
    bank = Contact.create(name="Bank", now=NOW)
    persons = [Person(UserId(new_id()), "Max Nord")]
    named = Holder(HolderKind.RECIPIENT, HolderSource.RULE, "Max Nord")
    once = [seen(bank.id, IBAN, 3, holder=named)]
    (item,) = open_identifiers([bank], once, persons=persons)
    assert (item.source, advice(item)) == (OpenSource.SUGGESTED, None)
    twice = [*once, seen(bank.id, IBAN, 4, holder=named)]
    (item,) = open_identifiers([bank], twice, persons=persons)
    assert advice(item) == (Recommendation.CONFIRM, ReasonCode.RECOMMEND_CONFIRM_NAMED)
