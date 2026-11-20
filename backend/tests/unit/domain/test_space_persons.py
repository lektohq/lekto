"""The persons a document names in the judge's rule for the space (`verdict.judge_space`), and
the model's recipient as a person (`verdict.recipient_persons`)."""

from functools import partial

from lekto.core.domain.facts import Strength
from lekto.core.domain.ids import SpaceId, UserId, new_id
from lekto.core.domain.pipeline import Outcome
from lekto.core.domain.verdict import (
    ClassifierView,
    FactsView,
    ModelProposal,
    Neighbour,
    Signals,
    SpaceOption,
    named_persons,
    recipient_persons,
)
from tests import builders
from tests.unit.domain import verdict_support
from tests.unit.domain.verdict_support import ERIKA, ERIKAS, HOUSEHOLD, JOHN, OWN, judge_space

BOB = UserId(new_id())
BOBS = SpaceId(new_id())
FAMILY = SpaceId(new_id())  # John, Erika and their child Bob
OPTIONS = {
    **verdict_support.OPTIONS,
    BOBS: SpaceOption("another user's personal space", frozenset({BOB}), personal_of=BOB),
}
choice = partial(verdict_support.choice, options=OPTIONS)


def sure_of(space: SpaceId) -> Signals:
    """The model and the classifier name `space`: the judge is sure of it."""
    return Signals(
        model=ModelProposal(space=space),
        classifier=ClassifierView(spaces=[(space, 0.95)], known_spaces=frozenset(OPTIONS)),
    )


def test_erika_s_identifier_alone_suggests_handing_it_over() -> None:
    """John uploads Erika's tax assessment: no signal names a space, her tax ID stands in it."""
    check = judge_space(Signals(), choice(), persons={ERIKA: Strength.HARD})
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(ERIKAS)
    assert check.value is None
    # Erika is new there: it shows the document to more people (a hand-over among them).
    assert str(check.reason).endswith("which shows it to more people")
    assert check.unseen_by == ()  # Erika sees it where the check leads
    # Names stay out of what is stored, ids only: the service shows it
    # (`test_space_suggestion.named_by_kind`).


def test_hard_evidence_against_a_sure_choice_makes_it_uncertain() -> None:
    """The signals are sure it stays with John; Erika's identifier says otherwise."""
    check = judge_space(sure_of(OWN), choice(), persons={ERIKA: Strength.HARD})
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(ERIKAS)


def test_hard_evidence_backs_a_space_a_signal_names() -> None:
    """The joint account names both; the model names Haushalt: sure, and suggested (wider)."""
    signals = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        classifier=ClassifierView(known_spaces=frozenset(OPTIONS)),
    )
    without = judge_space(signals, choice())
    assert without.outcome is Outcome.OK  # the model alone, and the classifier knows Haushalt
    assert without.value is None
    backed = judge_space(signals, choice(), persons={JOHN: Strength.HARD, ERIKA: Strength.HARD})
    assert backed.outcome is Outcome.UNCERTAIN
    assert backed.suggestion == str(HOUSEHOLD)
    assert backed.reason == "suggests another space, which shows it to more people"


def test_hard_evidence_of_two_backs_the_smallest_space_of_both() -> None:
    options = {**OPTIONS, FAMILY: SpaceOption("a shared space", frozenset({JOHN, ERIKA, BOB}))}
    del options[HOUSEHOLD]
    check = judge_space(
        Signals(), choice(options=options), persons={JOHN: Strength.HARD, ERIKA: Strength.HARD}
    )
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(FAMILY)


def test_the_uploader_s_own_evidence_only_confirms_staying() -> None:
    check = judge_space(Signals(), choice(), persons={JOHN: Strength.HARD})
    assert check.outcome is Outcome.OK
    assert check.value is None
    assert check.suggestion is None
    assert check.unseen_by == ()


def test_medium_evidence_only_warns() -> None:
    """Erika's birth date or the model's recipient: never yellow, the check lists her."""
    check = judge_space(Signals(), choice(), persons={ERIKA: Strength.MEDIUM})
    assert check.outcome is Outcome.OK
    assert check.suggestion is None
    assert check.unseen_by == (str(ERIKA),)
    assert check.reason == "names someone who would not see it there"


def test_a_warning_follows_the_suggestion() -> None:
    """Suggested Haushalt: Erika sees it there, Bob (named by his birth date) does not."""
    check = judge_space(
        sure_of(HOUSEHOLD), choice(), persons={ERIKA: Strength.MEDIUM, BOB: Strength.MEDIUM}
    )
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(HOUSEHOLD)
    assert check.unseen_by == (str(BOB),)
    assert check.reason == "suggests another space, which shows it to more people"


def test_weak_evidence_only_breaks_ties() -> None:
    """Unsure (the model names Erika's space, the classifier Haushalt): no move, no warning.
    Neither named, Bob's space likelier: Haushalt, where Erika (named) sees it, comes first."""
    signals = Signals(
        model=ModelProposal(space=ERIKAS),
        classifier=ClassifierView(spaces=[(HOUSEHOLD, 0.95)], known_spaces=frozenset(OPTIONS)),
    )
    check = judge_space(signals, choice(), persons={ERIKA: Strength.WEAK})
    assert check.outcome is Outcome.OK
    assert check.unseen_by == ()
    assert check.value is None
    tied = judge_space(
        Signals(classifier=ClassifierView(spaces=[(BOBS, 0.5), (HOUSEHOLD, 0.45)])),
        choice(),
        persons={ERIKA: Strength.WEAK, JOHN: Strength.WEAK},
    )
    assert tied.outcome is Outcome.OK
    assert tied.suggestion == str(HOUSEHOLD)


def test_persons_never_change_a_space_a_person_chose() -> None:
    check = judge_space(Signals(), choice(locked=True), persons={ERIKA: Strength.HARD})
    assert check.outcome is Outcome.OK
    assert check.suggestion is None
    assert check.unseen_by == ()


def test_two_others_without_a_space_of_their_own_warn_but_stay() -> None:
    """Erika's and Bob's identifiers, no space shows it to both and not to more: unsure, it
    stays, the check lists both."""
    check = judge_space(Signals(), choice(), persons={ERIKA: Strength.HARD, BOB: Strength.HARD})
    assert check.outcome is Outcome.OK
    assert check.value is None
    assert set(check.unseen_by) == {str(ERIKA), str(BOB)}


def test_the_recipient_names_every_user_it_contains() -> None:
    people = [(JOHN, ("John Doe", "Johnny")), (ERIKA, ("Jane Doe",)), (BOB, ("Bob",))]
    found = recipient_persons("John und Jane Doe", people, builders.THRESHOLDS)
    assert found == {ERIKA: Strength.MEDIUM}  # "John Doe" does not stand whole in it
    assert recipient_persons("Frau Jane Doe", people, builders.THRESHOLDS) == {
        ERIKA: Strength.MEDIUM
    }
    assert recipient_persons("Herrn John Doe", people, builders.THRESHOLDS) == {
        JOHN: Strength.MEDIUM
    }
    assert recipient_persons("Jane Do", people, builders.THRESHOLDS) == {
        ERIKA: Strength.MEDIUM
    }  # close enough
    assert recipient_persons("Stadtwerke Musterstadt", people, builders.THRESHOLDS) == {}
    assert recipient_persons(None, people, builders.THRESHOLDS) == {}


def test_the_strongest_evidence_counts() -> None:
    merged = named_persons({ERIKA: Strength.WEAK, BOB: Strength.HARD}, {ERIKA: Strength.MEDIUM})
    assert merged == {ERIKA: Strength.MEDIUM, BOB: Strength.HARD}


def test_facts_view_persons_reach_the_judge_through_signals() -> None:
    """The facts' persons as the judge node merges them with the recipient's."""
    signals = Signals(facts=FactsView(persons={ERIKA: Strength.HARD}))
    persons = named_persons(signals.facts.persons if signals.facts else {})
    check = judge_space(signals, choice(), persons=persons)
    assert check.suggestion == str(ERIKAS)


def test_it_stays_where_everyone_named_sees_it() -> None:
    """In Haushalt, the signals sure of John's own space, Erika's number in it: staying keeps it
    with both, no hand-over, no narrowing that leaves her out."""
    check = judge_space(sure_of(OWN), choice(current=HOUSEHOLD), persons={ERIKA: Strength.HARD})
    assert check.outcome is Outcome.OK
    assert check.value is None and check.suggestion is None
    assert "suggests" not in str(check.reason)


def test_the_joint_account_in_the_household_stays() -> None:
    both = {ERIKA: Strength.HARD, JOHN: Strength.HARD}
    check = judge_space(sure_of(OWN), choice(current=HOUSEHOLD), persons=both)
    assert (check.outcome, check.value, check.suggestion) == (Outcome.OK, None, None)


def test_a_recipient_two_users_match_alike_names_neither() -> None:
    people = [(ERIKA, ("Jane Doe",)), (BOB, ("Jana Doe",))]
    assert recipient_persons("Jan Doe", people, builders.THRESHOLDS) == {}


def payslip_signals(proposed: SpaceId = ERIKAS) -> Signals:
    """Erika's payslip uploaded by John: the model proposes `proposed`; John's five payslips,
    the most similar documents, all lie in his personal space (there was no one else); the
    classifier knows no spaces yet."""
    neighbours = tuple(
        Neighbour(document=str(new_id()), contact=None, document_type=None, space=OWN)
        for _ in range(5)
    )
    return Signals(model=ModelProposal(space=proposed), neighbours=neighbours)


def test_the_model_and_its_recipient_suggest_handing_it_over() -> None:
    """Tobi, 22.10.2026: the model proposes Erika's personal space and reads Erika as the
    recipient; the similar documents stay with John. Without the recipient the signals only
    disagree; with it Lekto suggests the hand-over (a click, never automatic)."""
    persons = {ERIKA: Strength.MEDIUM}
    without = judge_space(payslip_signals(), choice(), persons=persons)
    assert without.outcome is Outcome.OK
    assert without.value is None  # it stays
    check = judge_space(payslip_signals(), choice(), persons=persons, recipients=frozenset({ERIKA}))
    assert check.outcome is Outcome.UNCERTAIN
    assert check.value is None
    assert check.suggestion == str(ERIKAS)
    assert check.reason == "suggests another space, which shows it to more people"
    assert "erika" not in str(check.reason).lower()
    proposed = next(item for item in check.candidates if item.value == str(ERIKAS))
    assert any(source.recipient for source in proposed.sources)
    stays = next(item for item in check.candidates if item.value == str(OWN))
    assert not any(source.recipient for source in stays.sources)


def test_a_letter_to_both_is_no_hand_over() -> None:
    """The recipient names John and Erika: handing it over would leave John without it."""
    check = judge_space(
        payslip_signals(),
        choice(),
        persons={ERIKA: Strength.MEDIUM, JOHN: Strength.MEDIUM},
        recipients=frozenset({ERIKA, JOHN}),
    )
    assert check.outcome is Outcome.OK  # stays, with a warning that Erika does not see it
    assert check.value is None
    assert check.unseen_by == (str(ERIKA),)


def test_the_recipient_alone_moves_nothing() -> None:
    """The model proposes Haushalt, the recipient is Erika: no hand-over the model did not
    propose; and the model proposing Erika's space without her as recipient changes nothing."""
    household = judge_space(payslip_signals(HOUSEHOLD), choice(), recipients=frozenset({ERIKA}))
    assert (household.outcome, household.value) == (Outcome.OK, None)  # it stays
    # The model's space beside it, as signals that disagree give one: no review.
    assert household.suggestion == str(HOUSEHOLD)
    assert [reason.text for reason in household.reasons] == ["the signals name different spaces"]
    unaddressed = judge_space(payslip_signals(), choice(), recipients=frozenset({BOB}))
    assert unaddressed.outcome is Outcome.OK
    assert unaddressed.value is None


def test_already_in_erika_s_space_it_stays() -> None:
    """The model names her space, the similar documents John's: it stays where it lies, with
    Tobi's space beside it, as signals that disagree give one (Tobi, 19.11.2026: wanted)."""
    check = judge_space(payslip_signals(), choice(ERIKAS), recipients=frozenset({ERIKA}))
    assert (check.outcome, check.value) == (Outcome.OK, None)
    assert check.suggestion == str(OWN)
    assert [reason.text for reason in check.reasons] == ["the signals name different spaces"]
