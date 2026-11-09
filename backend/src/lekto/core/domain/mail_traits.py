"""What a mail is marked with, besides its addresses and subject (Tobi, 05.11.2026): its
importance, as the sender gave it, and its marks on the server, the keywords and the flag.

- Importance comes from the header: `Importance` (high, normal, low), `X-Priority` (1 and 2
  high, 4 and 5 low), `Priority` (urgent, non-urgent) or `X-MSMail-Priority`; normal without.
- Keywords are the IMAP keywords of the mail (RFC 3501: flags without a backslash), such as
  Thunderbird's tags or ones of Lekto's own. A server stores keywords of its own only when its
  PERMANENTFLAGS hold `\\*`. Keywords compare regardless of case, as IMAP has them.
- The flag (`\\Flagged`) has a colour as Apple Mail sets it: three keywords `$MailFlagBit0` to
  `$MailFlagBit2` give the number of the colour (0 red, 1 orange, 2 yellow, 3 green, 4 blue,
  5 purple, 6 grey). Other clients show a flag only; it reads as red.

Mail rules and document rules look at these alike (`mail_rules`, `rule_conditions`).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from lekto.core.domain.errors import ValidationError


class Importance(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class FlagColor(StrEnum):
    """Apple Mail's colours of a flag, in the order of their numbers."""

    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    GRAY = "gray"


FLAGGED = "\\Flagged"
SEEN = "\\Seen"
COLOR_BITS = ("$MailFlagBit0", "$MailFlagBit1", "$MailFlagBit2")
MAX_KEYWORD = 100
MAX_MAIL_TEXT = 500
"""The longest text a condition on a mail's sender, recipients or subject compares."""

_TEXT_OPERATORS = frozenset({"contains", "is", "starts_with", "ends_with"})
MAIL_OPERATORS: Mapping[str, frozenset[str]] = {
    "sender": _TEXT_OPERATORS,
    "recipient": _TEXT_OPERATORS,
    "to": _TEXT_OPERATORS,
    "cc": _TEXT_OPERATORS,
    "subject": _TEXT_OPERATORS,
    "importance": frozenset({"is"}),
    "keyword": frozenset({"contains", "present", "missing"}),
    "flag": frozenset({"is", "present", "missing"}),
}
"""The operators of each field of a mail both kinds of rule look at; mail rules add the folder and
the attachments, document rules the mailbox. A rule's own enums are built from this."""
_COLORS = tuple(FlagColor)
_BITS = frozenset(bit.casefold() for bit in COLOR_BITS)
_UNSHOWN = frozenset(
    name.casefold()
    for name in (
        "$Forwarded",
        "Forwarded",
        "$MDNSent",
        "$Junk",
        "Junk",
        "$NotJunk",
        "NotJunk",
        "NonJunk",
        "$Phishing",
        "$NotPhishing",
        "Redirected",
        "$Submitted",
        "$SubmitPending",
        "$iCloudCleanup",
        "$Important",
    )
)
"""Keywords clients set for themselves (a forward, a verdict on spam): not offered to choose."""


@dataclass(frozen=True)
class MailMarks:
    """The marks of a mail on the server: its keywords, as the server gives them, and its flag's
    colour (none: not flagged)."""

    keywords: tuple[str, ...] = ()
    flag: FlagColor | None = None

    @classmethod
    def of_flags(cls, flags: Iterable[str]) -> "MailMarks":
        """The marks of a mail's IMAP flags; the colour bits are no keywords of their own."""
        names = list(flags)
        folded = {name.casefold() for name in names}
        flag = None
        if FLAGGED.casefold() in folded:
            number = sum(
                1 << index for index, bit in enumerate(COLOR_BITS) if bit.casefold() in folded
            )
            flag = _COLORS[number] if number < len(_COLORS) else FlagColor.RED
        keywords = sorted(
            {name for name in names if not name.startswith("\\") and name.casefold() not in _BITS},
            key=str.casefold,
        )
        return cls(keywords=tuple(keywords), flag=flag)

    def has(self, keyword: str) -> bool:
        wanted = keyword.casefold()
        return any(item.casefold() == wanted for item in self.keywords)


def flag_bits(color: FlagColor) -> tuple[str, ...]:
    """The keywords that give a flag `color` in Apple Mail."""
    number = _COLORS.index(color)
    return tuple(bit for index, bit in enumerate(COLOR_BITS) if number & (1 << index))


def shown_keywords(flags: Iterable[str]) -> tuple[str, ...]:
    """The keywords among `flags` a person may want to choose: no system flags, colour bits or
    clients' own ones, sorted."""
    return tuple(
        sorted(
            {
                name
                for name in flags
                if name
                and not name.startswith("\\")
                and name.casefold() not in _BITS
                and name.casefold() not in _UNSHOWN
            },
            key=str.casefold,
        )
    )


def importance_of(headers: Mapping[str, str | None]) -> Importance:
    """The importance a mail's header gives, normal without one; `headers` by lowercase name."""
    importance = (headers.get("importance") or "").strip().casefold()
    if importance in ("high", "low"):
        return Importance(importance)
    priority = (headers.get("x-priority") or "").strip()[:1]
    if priority in ("1", "2"):
        return Importance.HIGH
    if priority in ("4", "5"):
        return Importance.LOW
    match (headers.get("priority") or "").strip().casefold():
        case "urgent":
            return Importance.HIGH
        case "non-urgent":
            return Importance.LOW
    ms = (headers.get("x-msmail-priority") or "").strip().casefold()
    if ms in ("high", "low"):
        return Importance(ms)
    return Importance.NORMAL


# --- what the conditions of both kinds of rule ask --------------------------------------------


@dataclass(frozen=True, kw_only=True)
class MailHead:
    """What a mail's head says, as the conditions of both kinds of rule look at it
    (`mail_rules.MailFacts`, `rule_conditions.MailOf`): the texts of each address field (an
    address and a name each; `recipients` is To and Cc together), the subject, the importance
    and the marks on the server (none for a mail fetched before Lekto read them: their
    conditions hold nothing)."""

    senders: tuple[str, ...]
    recipients: tuple[str, ...]
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str
    importance: Importance | None = None
    marks: MailMarks | None = None

    def texts(self, field: str) -> tuple[str, ...]:
        """The texts of `field`: `sender`, `recipient` (To or Cc), `to`, `cc` or `subject`."""
        match field:
            case "sender":
                return self.senders
            case "recipient":
                return self.recipients
            case "to":
                return self.to
            case "cc":
                return self.cc
            case "subject":
                return (self.subject,)
        raise ValueError(f"a mail's head has no texts of {field!r}")

    def text_holds(self, field: str, op: str, wanted: str) -> bool:
        """Whether a text of `field` `is`, `starts_with`, `ends_with` or (any other `op`)
        contains `wanted`, regardless of case."""
        wanted = wanted.casefold()
        return any(_compare(op, text.casefold(), wanted) for text in self.texts(field))


def _compare(op: str, text: str, wanted: str) -> bool:
    match op:
        case "is":
            return text == wanted
        case "starts_with":
            return text.startswith(wanted)
        case "ends_with":
            return text.endswith(wanted)
    return wanted in text


def importance_holds(importance: Importance | None, wanted: str) -> bool:
    """`is`: unknown (a mail fetched before Lekto read it) holds nothing."""
    return importance is not None and importance.value == wanted


def keyword_holds(marks: MailMarks | None, op: str, wanted: str | None) -> bool:
    """`contains` a keyword, `present` any, `missing` none; unknown marks hold nothing."""
    if marks is None:
        return False
    match op:
        case "present":
            return bool(marks.keywords)
        case "missing":
            return not marks.keywords
    return wanted is not None and marks.has(wanted)


def flag_holds(marks: MailMarks | None, op: str, wanted: str | None) -> bool:
    """`present` flagged, `missing` not, `is` flagged in colour `wanted`; unknown marks hold
    nothing."""
    if marks is None:
        return False
    match op:
        case "present":
            return marks.flag is not None
        case "missing":
            return marks.flag is None
    return marks.flag is not None and marks.flag.value == wanted


def is_keyword(value: str) -> bool:
    """A keyword IMAP can carry: an atom of 1 to `MAX_KEYWORD` printable ASCII characters,
    without a backslash or one of `(){ %*"]`."""
    return (
        0 < len(value) <= MAX_KEYWORD
        and value.isascii()
        and all(32 < ord(char) < 127 and char not in '(){ %*"\\]' for char in value)
    )


def check_mail_value(field: str, value: object, *, label: str) -> None:
    """Check the value a condition (or a step) compares a mail's `field` with: a text of 1 to
    `MAX_MAIL_TEXT` characters, an importance, a flag's colour or a keyword. `label` names it in
    the message (`flag`, `mail_flag`, `add_keyword`)."""
    if not isinstance(value, str):
        raise ValidationError(f"{label}: expected text, got {value!r}")
    match field:
        case "importance":
            if value not in {item.value for item in Importance}:
                raise ValidationError(f"{label}: high, normal or low")
        case "flag":
            if value not in {item.value for item in FlagColor}:
                raise ValidationError(f"{label}: a colour, not {value!r}")
        case "keyword":
            if not is_keyword(value):
                raise ValidationError(f"{label}: not one IMAP can carry: {value!r}")
        case _:
            if not value.strip() or len(value) > MAX_MAIL_TEXT:
                raise ValidationError(f"{label}: a value of 1 to {MAX_MAIL_TEXT} characters")
