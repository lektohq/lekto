"""Limits more than one inbound adapter (REST, MCP) names, and how their texts spell numbers.

The descriptions of the API are the contract clients read: they take the numbers from the
constants, so that a changed limit changes its text too.
"""

MAX_SELECTED = 100
"""Documents the list names by id at most (`ids`): the API refuses more, the MCP server links no
more, the web UI selects no more."""

_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def in_words(number: int) -> str:
    """`number` as an English word up to ten, as digits beyond."""
    return _WORDS[number] if 0 <= number < len(_WORDS) else str(number)
