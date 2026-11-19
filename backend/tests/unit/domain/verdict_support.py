"""What the tests of the judge's rule for the space share (`verdict.judge_space`): the people,
their spaces, and a choice among them."""

from functools import partial

from lekto.core.domain import verdict
from lekto.core.domain.ids import SpaceId, UserId, new_id
from lekto.core.domain.verdict import SpaceChoice, SpaceOption
from tests import builders

judge_space = partial(verdict.judge_space, thresholds=builders.THRESHOLDS)

TOBI, ERIKA = UserId(new_id()), UserId(new_id())
OWN, HOUSEHOLD, ERIKAS = SpaceId(new_id()), SpaceId(new_id()), SpaceId(new_id())
SHARED_OWN = SpaceId(new_id())  # Tobi's personal space, shared with Erika
OPTIONS = {
    OWN: SpaceOption("the uploader's personal space", frozenset({TOBI}), personal_of=TOBI),
    HOUSEHOLD: SpaceOption("a shared space", frozenset({TOBI, ERIKA})),
    ERIKAS: SpaceOption("another user's personal space", frozenset({ERIKA}), personal_of=ERIKA),
}


def choice(
    current: SpaceId = OWN,
    *,
    locked: bool = False,
    options: dict[SpaceId, SpaceOption] | None = None,
) -> SpaceChoice:
    """Tobi's upload in `current` among `options` (`OPTIONS`); in `SHARED_OWN`, that one too."""
    chosen = dict(options or OPTIONS)
    if current == SHARED_OWN:
        chosen[SHARED_OWN] = SpaceOption(
            "the uploader's personal space", frozenset({TOBI, ERIKA}), personal_of=TOBI
        )
    return SpaceChoice(current=current, options=chosen, locked=locked, uploader=TOBI)
