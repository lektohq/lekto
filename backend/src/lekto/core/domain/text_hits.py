"""Where a rule's text conditions hit a document's text, as characters of the text as stored,
for showing them on its pages. Each searches the text the rules read, traced back to the text
as stored (`traced.Traced`): `contains` the normalised text as `evidence.contains` reads it
(whole words, umlauts either way, or, for a long value, without spaces), `matches` the text
without markup as `rule_conditions.pattern_text` gives it to a pattern."""

import re

from lekto.core.domain.evidence import (
    SHORTEST_SPACELESS,
    fold_umlauts,
    normalise,
    traced_normalise,
    traced_without_markup,
    whole_words,
)
from lekto.core.domain.traced import Traced

MAX_HITS = 20
"""Places of one condition at most."""

_SPACE = re.compile(" ")


def contained(text: str, value: str) -> tuple[tuple[int, int], ...]:
    """Where `text` contains `value` as `evidence.contains` finds it, as characters of `text`."""
    needle = normalise(value)
    if not needle:
        return ()
    normalised = traced_normalise(text)
    found = _spans(whole_words(needle), normalised)
    if not found:
        found = _spans(whole_words(fold_umlauts(needle)), normalised.each(fold_umlauts))
    spaceless = needle.replace(" ", "")
    if not found and len(spaceless) >= SHORTEST_SPACELESS:
        found = _spans(re.compile(re.escape(spaceless)), normalised.sub(_SPACE, ""))
    return found


def pattern_text(text: str, limit: int) -> Traced:
    """The text a pattern runs against in the rules (`rule_conditions.pattern_text`), traced
    to `text`."""
    return traced_without_markup(text[: limit * 2]).head(limit)


def _spans(pattern: re.Pattern[str], traced: Traced) -> tuple[tuple[int, int], ...]:
    found = pattern.finditer(traced.text)
    return tuple(
        traced.span(*match.span()) for _, match in zip(range(MAX_HITS), found, strict=False)
    )
