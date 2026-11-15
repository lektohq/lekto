"""Small checks shared by the domain model."""

import re
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.reasons import ReasonCode, because

MAX_NAME = 200
"""Characters of a name: contacts, types, tags, fields, spaces, rules, aliases, choices. The
REST schemas take their limit from here."""

MAX_REFERENCES = 1000
"""Ids in one list of a request that name other objects with no limit of their own: the members
of a space, the spaces of a user being removed, the order of lenses, the document types of a
field. More than there can be of them is no request; the REST schemas take the limit from here."""


def require_utc(value: datetime, what: str = "timestamp") -> datetime:
    """Timestamps are timezone-aware and in UTC; naive or offset times are rejected."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValidationError(f"{what} must be timezone-aware UTC, got {value.isoformat()}")
    return value.astimezone(UTC)


def require_name(value: str, what: str = "name", *, max_length: int | None = MAX_NAME) -> str:
    """Names are stripped, must not be empty and have at most `max_length` characters (None:
    no limit, for values that are not names of Lekto's own, such as file names)."""
    name = value.strip()
    if not name:
        raise ValidationError(because(ReasonCode.NAME_EMPTY, what=what))
    if max_length is not None and len(name) > max_length:
        raise ValidationError(because(ReasonCode.NAME_TOO_LONG, what=what, max=max_length))
    return name


MAX_FILENAME = 255
"""Characters of a file's name as Lekto keeps it: an upload, an attachment of a mail."""

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def without_control(text: str) -> str:
    """`text` without control characters (those below the space, and DEL): Postgres refuses NUL
    in text, the others garble what a person reads. Texts from outside (a file's name, a mail's
    subject and addresses) pass through here before Lekto keeps them."""
    return _CONTROL.sub("", text)


def clean_filename(raw: str) -> str:
    """The last path segment of a file's name as a client or a mail gives it, without control
    characters, at most `MAX_FILENAME` characters; empty if nothing is left (the caller names
    the file then)."""
    name = PurePosixPath(raw.replace("\\", "/")).name
    name = without_control(name).strip()[:MAX_FILENAME]
    return "" if name in (".", "..") else name


MAX_URL_LENGTH = 2000
"""Characters of a URL or a path on this site: a webhook's target, where to go after signing
in."""


def has_control_characters(text: str) -> bool:
    """Whether `text` holds a space, a control character or DEL: nothing a URL or a path on
    this site may contain."""
    return any(ord(char) < 0x21 or ord(char) == 0x7F for char in text)


def name_key(name: str) -> str:
    """Comparison key for names that are unique regardless of case."""
    return name.strip().casefold()
