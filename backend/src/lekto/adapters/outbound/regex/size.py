"""How much of a pattern `regex` spells out when it compiles it.

`regex` writes a counted repetition out as often as its lower bound says: `a{4000000}` becomes
four million items, `((a{200}){200}){200}` eight million, and compiling them takes seconds and
gigabytes in the process that compiles (measured with `regex` 2026.9.29: 1.9 s and 1 GB, 3.6 s
and 2.7 GB). No time limit stops that: the limit of the matcher holds for searching only. `*`,
`+`, `?`, back references and calls of groups are not spelled out, nor is the upper bound of a
range (`.{0,20000}` compiles at once).

`spelled_out` reads an upper bound from the pattern alone, without compiling it, so that the
matcher refuses such a pattern first (`MAX_SPELLED_OUT`). It may count too much, never too little:
a test holds it against what the parser of `regex` reads from the same pattern.
"""

import re
from dataclasses import dataclass

MAX_SPELLED_OUT = 10_000
"""Characters a pattern may spell out: compiling as many takes about 4 MB and a millisecond.
Patterns of rules come nowhere near it (an IBAN 39, `Rechnung.{0,500}Betrag` 514)."""

# A counted repetition: `{n}`, `{n,}`, `{,m}`, `{n,m}`, `{,}`. `{}` is two characters.
_COUNT = re.compile(r"\{([0-9]*)(,[0-9]*)?\}")
# What stands between a repetition and the item it repeats without taking the item's place, or
# is not spelled out: inline flags (`(?i)`), calls of groups (`(?1)`, `(?R)`, `(?&name)`) and
# back references by name (`(?P=name)`).
_PASSING = re.compile(r"\(\?(?:[\^a-zA-Z0-9+-]*|P[=>]\w+|&\w+)\)")
# The head of a group that is no item: `(?:`, `(?>`, `(?|`, `(?=`, `(?<!`, `(?P<name>`,
# `(?i-s:`. A head it does not know (`(?(1)`) leaves the rest to be read as items.
_HEAD = re.compile(r"\((?:\?(?:[:>|=!]|<[=!]|P?<\w+>|[\^a-zA-Z0-9-]*:))?")
# A flag group that may switch on verbose mode (`(?x)`, `(?ix:`, `(?-x)`); `regex` starts
# without it, so the first one stands in the pattern as written.
_VERBOSE = re.compile(r"\(\?[\^a-zA-Z0-9-]*x")


def spelled_out(pattern: str) -> int:
    """An upper bound of the characters `regex` spells out when it compiles `pattern`.

    It follows the pattern's structure: a literal, an escape, a set and `.` count one; a group
    counts its content (at least one), alternatives add up; a counted repetition multiplies the
    item before it by its largest number (`{2,500}` by 500), `*`, `+` and `?` do not multiply.
    Comments (`(?#…)`), inline flags and calls of groups count nothing and do not part a
    repetition from its item, as in `regex`.

    In verbose mode whitespace and `#` comments stand anywhere, inside a repetition's braces
    too, and part nothing. A pattern that may switch it on gets a coarser bound that holds for
    any reading: its length times every count in it.
    """
    if _VERBOSE.search(pattern):
        return _coarse(pattern)
    return _structured(pattern)


@dataclass
class _Group:
    before: int = 0  # the alternatives before the current one
    current: int = 0  # the current alternative
    last: int = 0  # its last item, which a repetition repeats

    @property
    def size(self) -> int:
        return self.before + self.current

    def add(self, size: int) -> None:
        self.current += size
        self.last = size

    def repeat(self, times: int) -> None:
        # Nothing to repeat (`|{3}`): `regex` refuses it; count an item rather than none.
        item = max(self.last, 1)
        self.current += item * times - self.last
        self.last = item * times

    def branch(self) -> None:
        self.before += self.current
        self.current = self.last = 0


def _structured(pattern: str) -> int:
    groups = [_Group()]
    at, end = 0, len(pattern)
    while at < end:
        char = pattern[at]
        group = groups[-1]
        if char == "\\":
            group.add(1)
            at += 2
        elif char == "[":
            group.add(1)
            at = _set_end(pattern, at)
        elif char == "(":
            if pattern.startswith("(?#", at):
                at = _comment_end(pattern, at)
            elif passing := _PASSING.match(pattern, at):
                at = passing.end()
            else:
                groups.append(_Group())
                head = _HEAD.match(pattern, at)
                at = head.end() if head else at + 1
        elif char == ")":
            if len(groups) > 1:
                _close(groups)
            at += 1
        elif char == "|":
            group.branch()
            at += 1
        elif char == "{" and (count := _COUNT.match(pattern, at)) and count.group() != "{}":
            group.repeat(_largest(count))
            at = count.end()
        else:
            if char not in "*+?":
                group.add(1)
            at += 1
    while len(groups) > 1:  # a group left open: `regex` refuses the pattern; count it anyway
        _close(groups)
    return groups[0].size


def _close(groups: list[_Group]) -> None:
    inner = groups.pop()
    groups[-1].add(max(inner.size, 1))


def _set_end(pattern: str, start: int) -> int:
    """Where the set at `start` ends: after the first `]` that is neither escaped nor its first
    character. It ends no later than `regex` ends it (a POSIX class ends it early), so that no
    repetition hides in it."""
    at = start + 1
    if pattern.startswith("^", at):
        at += 1
    if pattern.startswith("]", at):
        at += 1
    while at < len(pattern):
        if pattern[at] == "\\":
            at += 2
        elif pattern[at] == "]":
            return at + 1
        else:
            at += 1
    return len(pattern)


def _comment_end(pattern: str, start: int) -> int:
    """Where the comment at `start` (`(?#…)`) ends: after its first unescaped `)`."""
    at = start + 3
    while at < len(pattern):
        if pattern[at] == "\\":
            at += 2
        elif pattern[at] == ")":
            return at + 1
        else:
            at += 1
    return len(pattern)


def _largest(count: re.Match[str]) -> int:
    lower, upper = count.group(1), (count.group(2) or ",")[1:]
    return max(int(lower or 0), int(upper or 0), 1)


def _coarse(pattern: str) -> int:
    bound = max(len(pattern), 1)
    for at, char in enumerate(pattern):
        if char == "{":
            bound *= max(_braces(pattern, at, verbose=False), _braces(pattern, at, verbose=True))
    return bound


def _braces(pattern: str, start: int, *, verbose: bool) -> int:
    """The largest number of the repetition whose braces open at `start`, read with or without
    verbose mode; 1 if they are none."""
    read: list[str] = []
    at = start + 1
    while at < len(pattern):
        char = pattern[at]
        if verbose and char.isspace():
            at += 1
        elif verbose and char == "#":
            newline = pattern.find("\n", at)
            at = len(pattern) if newline < 0 else newline + 1
        elif char == "}":
            count = _COUNT.fullmatch("{" + "".join(read) + "}")
            return _largest(count) if count and read else 1
        elif char in "0123456789,":
            read.append(char)
            at += 1
        else:
            return 1
    return 1
