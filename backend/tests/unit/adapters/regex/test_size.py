"""How much of a pattern `regex` spells out when it compiles it: the bound counts what the
pattern's structure says and never less than the parser of `regex` reads."""

import random
import warnings

import pytest
import regex
from regex import _regex_core as core

from lekto.adapters.outbound.regex.size import MAX_SPELLED_OUT, spelled_out


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("", 0),
        ("abc", 3),
        ("a{5}", 5),
        ("a{2,7}", 7),  # the larger number, although `regex` spells out the smaller
        ("a{3,}", 3),
        ("a{,9}", 9),
        ("a{,}", 1),
        ("a{}", 3),  # no repetition: three characters
        ("a{x}", 4),
        ("a{ 3 }", 6),  # without verbose mode no repetition
        ("(ab){3}", 6),
        ("(?:a{2}|b{5}){3}", 21),
        ("((a{2}){3}){4}", 24),
        ("a*b+c?", 3),
        ("a{3}?", 3),
        ("a{3}+", 3),
        (r"\d{4}-\d{4}", 9),
        (r"\{1000000}", 9),  # an escaped brace: no repetition
        ("[{]{4}", 4),
        ("[]{]{4}", 4),  # `]` first in a set is a character
        ("[^]a]{3}", 3),
        (r"[\]]{3}", 3),
        ("[[:alpha:]]{4}", 5),  # ends the set early: one `]` too many, never too few
        (r"\p{L}{4}", 7),  # the braces of a property count as characters
        ("(a{10})(?#x){10}", 100),  # a comment does not part a repetition from its item
        (r"(a{10})(?#x\)y){10}", 100),
        ("(a{10})(?i){10}", 100),
        ("(a{5})(?1){10}", 50),
        (r"(a{5})\1{10}", 15),
        ("(?P<n>a{3}){2}", 6),
        ("(?<n>a{3}){2}", 6),
        ("(?<=a{3})b", 4),
        ("(?>a{3}|b){2}", 8),
        ("(a{5}", 5),  # left open
        ("|{3}", 3),
        (r"[A-Z]{2}\d{2}(?: ?\d{4}){4,7}", 39),
        ("Rechnung.{0,500}Betrag", 514),
        ("((a{200}){200}){200}", 8_000_000),
    ],
)
def test_counts_what_the_structure_spells_out(pattern: str, expected: int) -> None:
    assert spelled_out(pattern) == expected


@pytest.mark.parametrize(
    "pattern",
    [
        "(?x)(a{1000}) {1000}",
        "(?x)(a{1000})#c\n{1000}",
        "(?x)a{1 000 000}",
        "(?x)a{1000000#c\n}",
        "(?x:b)(a{1000})#{1000}",
    ],
)
def test_verbose_mode_counts_every_repetition(pattern: str) -> None:
    assert spelled_out(pattern) > MAX_SPELLED_OUT


def test_a_verbose_pattern_counts_its_length_times_every_count() -> None:
    assert spelled_out("(?x) a{3} b{4}") == len("(?x) a{3} b{4}") * 3 * 4


@pytest.mark.parametrize(
    "pattern",
    [
        "a{4000000}",
        "(a{2000}){2000}",
        "((a{200}){200}){200}",
        "(?:a{2}|b{2000}){1000}",
        "(a?){50000}",
        "[[:alpha:]]{1000000}",
        "[[:a]{1000000}x:]",
        r"\p{L}{1000000}",
        r"\x41{1000000}",
        "(a{1000})(?#x){1000}",
        "(a{1000})(?i){1000}",
        "(a{1000}){1000}?",
        "a{1000000,}",
    ],
)
def test_the_patterns_that_take_gigabytes_are_too_large(pattern: str) -> None:
    """Each takes between 30 MB and 2.7 GB to compile (measured)."""
    assert spelled_out(pattern) > MAX_SPELLED_OUT


# --- against the parser of `regex` ------------------------------------------------------------


def spelled_by_regex(pattern: str) -> int:
    """What `regex` spells out: each repetition's body as often as its lower bound, at least
    once; read from its own parse of `pattern` (its private parser, for this test only)."""
    flags = regex.VERSION0
    while True:
        source = core.Source(pattern)
        info = core.Info(flags, source.char_type, {})
        source.ignore_space = bool(info.flags & core.VERBOSE)
        try:
            return _walk(core._parse_pattern(source, info))
        except core._UnscopedFlagSet:
            flags = info.global_flags


def _walk(node: object) -> int:
    if isinstance(node, core.GreedyRepeat):  # also lazy and possessive
        return _walk(node.subpattern) * max(int(node.min_count), 1)
    if isinstance(node, core.Sequence):
        return sum(_walk(item) for item in node.items)
    if isinstance(node, core.Branch):
        return sum(_walk(branch) for branch in node.branches)
    if isinstance(node, core.String):
        return len(node.characters)
    parts = [getattr(node, name, None) for name in ("subpattern", "yes_item", "no_item")]
    present = [part for part in parts if part is not None and hasattr(part, "__dict__")]
    return sum(_walk(part) for part in present) if present else 1


def test_the_reference_reads_what_regex_spells_out() -> None:
    assert spelled_by_regex("a{5}") == 5
    assert spelled_by_regex("a{2,7}") == 2
    assert spelled_by_regex("(a{10})(?#x){10}") == 100
    assert spelled_by_regex("(?x)(a{10})#c\n{10}") == 100
    assert spelled_by_regex("(?:a{2}|b{5}){3}") == 21


ATOMS = ["a", "b", "ab", ".", r"\d", r"\{", "[ab]", "[]a]", "[^]a]", r"\p{L}", "{", "}", "#", " "]
VERBOSE = ["(?x)", "(?-x)", "(?x:", "(?ix:", "(?-x:"]


def _generate(rng: random.Random, depth: int) -> str:
    parts: list[str] = []
    for _ in range(rng.randint(1, 4)):
        choice = rng.random()
        if depth < 3 and choice < 0.3:
            opening = rng.choice(["(", "(?:", "(?P<g>", "(?=", "(?>", *VERBOSE[2:]])
            inner = _generate(rng, depth + 1)
            if rng.random() < 0.3:
                inner += "|" + _generate(rng, depth + 1)
            item = opening + inner + ")"
        elif choice < 0.4:
            item = rng.choice([*VERBOSE[:2], "(?#c)", "(?i)", "#c\n", " ", "\n"])
        else:
            item = rng.choice(ATOMS)
        if rng.random() < 0.5:
            low = rng.randint(0, 40)
            item += rng.choice(
                [
                    f"{{{low}}}",
                    f"{{{low},{low + rng.randint(0, 40)}}}",
                    f"{{{low},}}",
                    f"{{,{low}}}",
                    f"{{ {low} }}",
                    f"{{{low}#c\n}}",
                    "*",
                    "+",
                    "?",
                ]
            ) + rng.choice(["", "", "?", "+"])
        parts.append(item)
    return "".join(parts)


def test_never_counts_less_than_regex_spells_out() -> None:
    rng = random.Random(20261107)
    compared = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(4000):
            pattern = _generate(rng, 0)
            try:
                spelled = spelled_by_regex(pattern)
            except (regex.error, KeyError, ValueError, RecursionError):
                continue
            compared += 1
            assert spelled_out(pattern) >= spelled, pattern
    assert compared > 1000
