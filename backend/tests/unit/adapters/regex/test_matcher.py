"""The `regex` pattern matcher passes the contract; its patterns behave like Python's `re`
(with which the domain checks them)."""

import re

import pytest

from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.adapters.outbound.regex.matcher import _compile
from lekto.adapters.outbound.regex.size import MAX_SPELLED_OUT
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.reasons import ReasonCode
from tests.contracts.patterns import PatternMatcherContract

TIMEOUT = 0.05  # seconds


@pytest.fixture
def pattern_matcher() -> RegexPatternMatcher:
    return RegexPatternMatcher(TIMEOUT)


class TestRegexPatternMatcher(PatternMatcherContract):
    pass


@pytest.mark.parametrize("timeout", [0, -1.0])
def test_the_time_limit_must_be_positive(timeout: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        RegexPatternMatcher(timeout)


async def test_patterns_follow_the_syntax_of_re(pattern_matcher: RegexPatternMatcher) -> None:
    """VERSION0: `--` in a set is a range as in `re`, not a set difference (VERSION1)."""
    pattern, text = "^[a-z--x]$", "x"
    with pytest.warns(FutureWarning):  # `re` warns of a possible set difference
        expected = re.search(pattern, text) is not None
    assert expected
    assert await pattern_matcher.search(pattern, text, case_sensitive=True) is expected


async def test_an_invalid_pattern_names_the_pattern(pattern_matcher: RegexPatternMatcher) -> None:
    with pytest.raises(ValidationError, match=r"invalid pattern '\('"):
        await pattern_matcher.search("(", "text", case_sensitive=False)


async def test_compiled_patterns_are_cached_per_case_setting(
    pattern_matcher: RegexPatternMatcher,
) -> None:
    pattern = "lekto-cache-test-[0-9]+"
    before = _compile.cache_info()
    for _ in range(3):
        assert await pattern_matcher.search(pattern, "lekto-cache-test-42", case_sensitive=True)
        assert await pattern_matcher.search(pattern, "LEKTO-CACHE-TEST-42", case_sensitive=False)
    after = _compile.cache_info()
    assert after.misses - before.misses == 2  # once per case setting
    assert after.hits - before.hits == 4
    assert _compile(pattern, True) is _compile(pattern, True)
    assert _compile(pattern, True) is not _compile(pattern, False)


def test_a_pattern_too_large_names_the_limit(pattern_matcher: RegexPatternMatcher) -> None:
    pattern_matcher.validate(f"a{{{MAX_SPELLED_OUT}}}")
    with pytest.raises(ValidationError, match="too large") as caught:
        pattern_matcher.validate(f"a{{{MAX_SPELLED_OUT + 1}}}")
    assert caught.value.reason.code is ReasonCode.PATTERN_TOO_LARGE
    assert caught.value.reason.params == {"pattern": "a{10001}", "max": MAX_SPELLED_OUT}


@pytest.mark.parametrize(
    ("pattern", "detail"),
    [
        ("(?V1)a", "V1 is not supported"),
        ("a(?V1)", "V1 is not supported"),
        ("(?iV1:a)", "V1 is not supported"),
        ("(?au)a", "mutually incompatible"),
        ("(?a)(?L)a", "mutually incompatible"),
    ],
)
async def test_flags_regex_cannot_combine_make_an_invalid_pattern(
    pattern_matcher: RegexPatternMatcher, pattern: str, detail: str
) -> None:
    """`regex` fails on them with a KeyError or a ValueError, not with its syntax error."""
    with pytest.raises(ValidationError, match=detail) as caught:
        pattern_matcher.validate(pattern)
    assert caught.value.reason.code is ReasonCode.PATTERN_INVALID
    for case_sensitive in (False, True):
        with pytest.raises(ValidationError, match=detail):
            await pattern_matcher.search(pattern, "a", case_sensitive=case_sensitive)
