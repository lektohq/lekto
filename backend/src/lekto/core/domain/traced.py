"""A text made from another one, with, for each of its characters, the characters of the other
it comes from: to show on a document's pages where something found in its normalised text
stands (`evidence.traced_normalise`)."""

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Traced:
    """`text`, its character `i` made of characters `start[i]` to `end[i]` (exclusive) of the
    text it was made from."""

    text: str
    start: tuple[int, ...]
    end: tuple[int, ...]

    @classmethod
    def of(cls, text: str) -> "Traced":
        """`text` as it is, each character its own."""
        return cls(text, tuple(range(len(text))), tuple(range(1, len(text) + 1)))

    def span(self, first: int, last: int) -> tuple[int, int]:
        """Characters `first` to `last` (exclusive, not empty) of `text`, in the text it was
        made from."""
        return self.start[first], self.end[last - 1]

    def sub(
        self, pattern: re.Pattern[str], replacement: str | Callable[[re.Match[str]], str]
    ) -> "Traced":
        """As `pattern.sub(replacement, text)`: what replaces a match comes from what it
        matched."""
        text: list[str] = []
        start: list[int] = []
        end: list[int] = []
        last = 0
        for match in pattern.finditer(self.text):
            first, after = match.span()
            text.append(self.text[last:first])
            start.extend(self.start[last:first])
            end.extend(self.end[last:first])
            new = replacement if isinstance(replacement, str) else replacement(match)
            if new and after > first:
                text.append(new)
                start.extend([self.start[first]] * len(new))
                end.extend([self.end[after - 1]] * len(new))
            last = after
        text.append(self.text[last:])
        start.extend(self.start[last:])
        end.extend(self.end[last:])
        return Traced("".join(text), tuple(start), tuple(end))

    def each(self, change: Callable[[str], str]) -> "Traced":
        """Each character changed by `change`, into none, one or more."""
        text: list[str] = []
        start: list[int] = []
        end: list[int] = []
        for index, character in enumerate(self.text):
            new = change(character)
            text.append(new)
            start.extend([self.start[index]] * len(new))
            end.extend([self.end[index]] * len(new))
        return Traced("".join(text), tuple(start), tuple(end))

    def grouped(self, starts: Callable[[str], bool], change: Callable[[str], str]) -> "Traced":
        """Each group of characters changed by `change`: a group begins with a character
        `starts` holds for and takes the ones after it it does not."""
        text: list[str] = []
        start: list[int] = []
        end: list[int] = []
        first = 0
        for index in range(1, len(self.text) + 1):
            if index < len(self.text) and not starts(self.text[index]):
                continue
            new = change(self.text[first:index])
            text.append(new)
            start.extend([self.start[first]] * len(new))
            end.extend([self.end[index - 1]] * len(new))
            first = index
        return Traced("".join(text), tuple(start), tuple(end))

    def strip(self) -> "Traced":
        """Without whitespace at either end (as `str.strip`)."""
        left = len(self.text) - len(self.text.lstrip())
        right = len(self.text.rstrip())
        return self.head(right).tail(left) if right > left else Traced("", (), ())

    def head(self, count: int) -> "Traced":
        """The first `count` characters."""
        return Traced(self.text[:count], self.start[:count], self.end[:count])

    def tail(self, skip: int) -> "Traced":
        """Without the first `skip` characters."""
        return Traced(self.text[skip:], self.start[skip:], self.end[skip:])
