"""Releases of Lekto and which of them is news to a running instance (Tobi, 19.11.2026,
`.knowledge/open/update-notifier-fas.md`).

A version follows Semver (`0.16.0`, `1.2.0-beta.1`). It is a beta below 1.0 or with a
pre-release, else stable, as the images' channels (`.github/scripts/image_tags.py`). A beta hears
of newer betas and stable releases, a stable release of newer stable ones only. The repository's
own version (`0.0.0.dev0`) is a development state: it hears of none.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from functools import total_ordering
from typing import Self

_VERSION = re.compile(
    r"v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
DEVELOPMENT = "0.0.0.dev0"
"""The version the repository carries between releases."""


@total_ordering
@dataclass(frozen=True)
class Version:
    """A version after Semver, ordered by its precedence (a pre-release before its release)."""

    text: str
    core: tuple[int, int, int]
    pre: tuple[str, ...] = ()

    @classmethod
    def parse(cls, tag: str) -> Self | None:
        """The version of a tag (`v0.16.0` or `0.16.0`); None for anything else."""
        found = _VERSION.fullmatch(tag.strip())
        if found is None:
            return None
        core = (int(found["major"]), int(found["minor"]), int(found["patch"]))
        pre = tuple(found["pre"].split(".")) if found["pre"] else ()
        return cls(tag.strip().removeprefix("v"), core, pre)

    @property
    def stable(self) -> bool:
        return self.core[0] >= 1 and not self.pre

    def _key(self) -> tuple[tuple[int, int, int], int, tuple[tuple[int, int | str], ...]]:
        identifiers = tuple((0, int(part)) if part.isdigit() else (1, part) for part in self.pre)
        return self.core, 0 if self.pre else 1, identifiers

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())


@dataclass(frozen=True, kw_only=True)
class Release:
    """A published release: its version, when it was published, its page with the notes."""

    version: str
    published_at: datetime
    url: str


def is_development(version: str) -> bool:
    """Whether `version` is no release: the repository's own, or anything not after Semver."""
    return version == DEVELOPMENT or Version.parse(version) is None


def newest_for(running: str, releases: list[Release]) -> Release | None:
    """The newest release of `releases` that is news to an instance running `running`: newer, and
    stable if `running` is; None if there is none, and for a development state."""
    current = None if is_development(running) else Version.parse(running)
    if current is None:
        return None
    found: tuple[Version, Release] | None = None
    for release in releases:
        version = Version.parse(release.version)
        if version is None or version <= current or (current.stable and not version.stable):
            continue
        if found is None or found[0] < version:
            found = (version, release)
    return None if found is None else found[1]


@dataclass(frozen=True, kw_only=True)
class UpdateCheck:
    """The last look at the releases: when, and the newest release that was news then (None if
    there was none)."""

    checked_at: datetime
    latest: Release | None


def update_available(running: str, latest: Release | None) -> bool:
    """Whether `latest` is newer than `running` (it may be older once the instance is updated)."""
    if latest is None or is_development(running):
        return False
    current, newest = Version.parse(running), Version.parse(latest.version)
    return current is not None and newest is not None and current < newest
