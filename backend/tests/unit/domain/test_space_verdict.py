"""The judge's rule for the space (`verdict.judge_space`)."""

from lekto.core.domain.classification import SPACE
from lekto.core.domain.ids import SpaceId, new_id
from lekto.core.domain.pipeline import Outcome
from lekto.core.domain.verdict import (
    ClassifierView,
    KnownLabels,
    ModelProposal,
    Neighbour,
    Signals,
    SpaceChoice,
    SpaceOption,
)
from tests.unit.domain.verdict_support import (
    ERIKA,
    ERIKAS,
    HOUSEHOLD,
    OPTIONS,
    OWN,
    SHARED_OWN,
    TOBI,
    choice,
    judge_space,
)


def neighbours(*spaces: SpaceId | None) -> tuple[Neighbour, ...]:
    return tuple(
        Neighbour(document=str(new_id()), contact=None, document_type=None, space=space)
        for space in spaces
    )


def test_two_signals_that_name_a_wider_space_suggest_it_without_naming_anyone() -> None:
    signals = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        classifier=ClassifierView(spaces=[(HOUSEHOLD, 0.9)], known_spaces=frozenset(OPTIONS)),
    )
    check = judge_space(signals, choice())
    assert check.field == SPACE
    assert check.outcome is Outcome.UNCERTAIN
    assert check.value is None
    assert check.suggestion == str(HOUSEHOLD)
    # Who reads the check may not see the space or its members: the web names them. That the
    # candidates name no one, the service shows (`test_space_suggestion.named_by_kind`).
    assert check.reason == "suggests another space, which shows it to more people"
    assert check.confidence < 0.9


def test_a_space_that_shows_it_to_no_one_new_is_moved_to() -> None:
    """From Tobi's shared personal space into Haushalt: Erika sees it in both."""
    signals = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        neighbours=neighbours(HOUSEHOLD, HOUSEHOLD, None),
        neighbours_know=KnownLabels(spaces=frozenset({HOUSEHOLD})),
    )
    check = judge_space(signals, choice(SHARED_OWN))
    assert check.outcome is Outcome.OK
    assert check.value == str(HOUSEHOLD)


def test_sure_of_the_space_it_lies_in_changes_nothing_and_is_no_model_value() -> None:
    """No value: rules that file the document elsewhere do not contradict the model."""
    for signals in (
        Signals(
            model=ModelProposal(space=OWN),
            classifier=ClassifierView(spaces=[(OWN, 0.95)], known_spaces=frozenset(OPTIONS)),
        ),
        Signals(model=ModelProposal(space=OWN)),  # the model alone, nothing else knows it
    ):
        check = judge_space(signals, choice())
        assert check.outcome is Outcome.OK
        assert check.value is None
        assert check.suggestion is None
        assert check.confidence == 1.0


def test_unsure_it_stays_and_is_never_uncertain() -> None:
    """The classifier alone names nothing the model does not; disagreeing signals neither."""
    alone = Signals(
        classifier=ClassifierView(spaces=[(HOUSEHOLD, 0.95)], known_spaces=frozenset(OPTIONS))
    )
    for signals in (
        alone,
        Signals(model=ModelProposal(space=ERIKAS), classifier=alone.classifier),
        Signals(),
    ):
        check = judge_space(signals, choice())
        assert check.outcome is Outcome.OK
        assert check.value is None
        assert check.confidence == 1.0
    disagreeing = judge_space(
        Signals(model=ModelProposal(space=ERIKAS), classifier=alone.classifier), choice()
    )
    assert disagreeing.reason == "the signals name different spaces"
    assert judge_space(alone, choice()).suggestion == str(HOUSEHOLD)


def test_the_model_alone_names_a_space_no_other_signal_knows() -> None:
    """Cold start: a new space the classifier and the neighbours never saw."""
    signals = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        classifier=ClassifierView(spaces=[(OWN, 0.6)], known_spaces=frozenset({OWN})),
    )
    check = judge_space(signals, choice())
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(HOUSEHOLD)
    covered = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        classifier=ClassifierView(spaces=[(OWN, 0.6)], known_spaces=frozenset({OWN, HOUSEHOLD})),
    )
    known = judge_space(covered, choice())
    assert known.outcome is Outcome.OK
    assert known.value is None


def test_a_space_a_person_decided_stays() -> None:
    signals = Signals(
        model=ModelProposal(space=HOUSEHOLD),
        classifier=ClassifierView(spaces=[(HOUSEHOLD, 0.95)], known_spaces=frozenset(OPTIONS)),
    )
    check = judge_space(signals, choice(locked=True))
    assert check.outcome is Outcome.OK
    assert check.value is None
    assert check.suggestion is None
    assert check.reason == "a person chose the space"


def test_a_space_the_uploader_cannot_file_into_is_none_of_the_candidates() -> None:
    elsewhere = SpaceId(new_id())
    signals = Signals(
        model=ModelProposal(space=elsewhere),
        classifier=ClassifierView(spaces=[(elsewhere, 0.99)], known_spaces=frozenset({elsewhere})),
    )
    check = judge_space(signals, choice())
    assert check.outcome is Outcome.OK
    assert check.value is None
    assert check.candidates == ()


def test_handing_over_is_a_wider_space_too() -> None:
    signals = Signals(
        model=ModelProposal(space=ERIKAS),
        neighbours=neighbours(ERIKAS, ERIKAS),
        neighbours_know=KnownLabels(spaces=frozenset({ERIKAS})),
    )
    check = judge_space(signals, choice())
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(ERIKAS)
    assert check.reason == "suggests another space, which shows it to more people"


def test_a_hand_over_that_narrows_is_still_only_suggested() -> None:
    """Tobi's personal space, which Erika reads; the model alone names Erika's personal space:
    no one new sees it, but Tobi would lose his upload. Lekto suggests the hand-over, it
    never hands over by itself."""
    check = judge_space(Signals(model=ModelProposal(space=ERIKAS)), choice(SHARED_OWN))
    assert check.outcome is Outcome.UNCERTAIN
    assert check.value is None
    assert check.suggestion == str(ERIKAS)
    assert check.reason == "suggests handing it over into another user's personal space"


def test_a_space_without_the_uploader_is_only_suggested() -> None:
    """From Haushalt into a space only Erika edits (not her personal one): Tobi, the uploader,
    would not see his document there."""
    erikas_archive = SpaceId(new_id())
    options = {
        **OPTIONS,
        erikas_archive: SpaceOption("a shared space", frozenset({ERIKA})),
    }
    signals = Signals(model=ModelProposal(space=erikas_archive))
    check = judge_space(signals, SpaceChoice(current=HOUSEHOLD, options=options, uploader=TOBI))
    assert check.outcome is Outcome.UNCERTAIN
    assert check.suggestion == str(erikas_archive)
    assert check.reason == "suggests a space its uploader does not see"
