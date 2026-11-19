"""A mail as Lekto reads it (`.eml`, RFC 5322 with MIME), with `email` of the standard library.

What a mail says about itself (sender, recipients, date, subject, Message-ID), its text (the HTML
part and the plain one, as far as there are), its attachments, the pictures its HTML shows by
`cid:`, and the mails attached to it, `MAX_FORWARDS` deep: one attached deeper stays an
attachment (`.eml`). A part that cannot be decoded is read with replacement characters rather
than failing the mail.

A header is read from its raw value, at most `MAX_RAW_HEADER` characters of it (`_raw`): the
standard library parses a list of addresses in a time that grows with its square, 16 000
recipients took 19 s.
"""

import email
import email.policy
import logging
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime
from functools import cached_property, partial

from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.mail_traits import Importance, importance_of
from lekto.core.domain.pixels import pixels
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.validation import MAX_NAME, clean_filename, without_control

log = logging.getLogger(__name__)

RFC822 = "message/rfc822"
MAX_FORWARDS = 5
"""Levels of attached mails read (`mail_intake.letters` unwraps them); a mail attached deeper
stays an attachment of the last (`.eml`). Each level is written again as the file of its mail
(`MailMessage.raw`): a hundred levels of 16 MB took 91 s and 1.6 GB."""
MAX_HEADER = 1000
"""Characters of a header value kept (a subject, a Message-ID)."""
MAX_RAW_HEADER = 10_000
"""Characters of the raw values of a header read at most, all of its lines together: a list of
addresses is cut at the last comma before (some 200 to 300 addresses)."""
MAX_ADDRESS = 254
"""Characters of an address at most (RFC 5321); a longer one is left out. A name is cut to
`MAX_NAME`."""
_SMTP = email.policy.SMTP.clone(refold_source="none")
"""Writes an attached mail's headers as they are: folding them again would parse them."""

_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Address:
    name: str
    address: str

    @property
    def shown(self) -> str:
        """`Name <address>`, or the address alone."""
        if self.name and self.name != self.address:
            return f"{self.name} <{self.address}>"
        return self.address


def address_line(addresses: Iterable[Address]) -> str:
    """The addresses as one line: `Name <address>, other@example.test`."""
    return ", ".join(address.shown for address in addresses)


def address_texts(addresses: Iterable[Address]) -> tuple[str, ...]:
    """The addresses and names, each for itself, as conditions on addresses look at them."""
    return tuple(text for item in addresses for text in (item.address, item.name) if text)


@dataclass(frozen=True)
class MailPart:
    """An attachment, or a picture of the HTML (`content_id`, without angle brackets)."""

    filename: str | None
    media_type: str
    data: bytes
    content_id: str | None = None
    inline: bool = False

    @cached_property
    def pixels(self) -> tuple[int, int] | None:
        """Width and height of an image, as its head says (`pixels.pixels`); None for another
        file or a head that does not say."""
        return pixels(self.data)


@dataclass(frozen=True, kw_only=True)
class MailMessage:
    sender: tuple[Address, ...]
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    subject: str
    date: datetime | None  # UTC
    message_id: str | None  # without angle brackets
    html: str | None
    text: str | None
    attachments: tuple[MailPart, ...]
    """Parts given as attachments, or inline with a file name and shown nowhere by `cid:` (as
    Apple Mail sends a PDF); attached mails aside (`messages`)."""
    pictures: tuple[MailPart, ...]
    """Parts the HTML can show by `cid:`."""
    messages: tuple["MailMessage", ...]
    """Mails attached to this one (a forward as attachment), `MAX_FORWARDS` deep."""
    source: bytes | Callable[[], bytes] = field(repr=False, compare=False, default=b"")
    """The mail as a file, or how to write it (`raw`)."""
    importance: Importance = Importance.NORMAL
    """As its header gives it (`mail_traits.importance_of`)."""

    @cached_property
    def raw(self) -> bytes:
        """The mail as a file (`.eml`): as received, or an attached one as it stands in it,
        written when first asked for: a mail that only wraps another needs none."""
        return self.source if isinstance(self.source, bytes) else self.source()


def read_mail(data: bytes) -> MailMessage:
    """The mail `data`; UnprocessableDocumentError if it has no header of a mail at all, or if
    reading it fails in any other way: a mail comes from anyone, and the mail intake records a
    mail it cannot read as failed and goes on with the next (mails attached a hundred deep make
    the standard library recurse too deep, for one)."""
    try:
        message = email.message_from_bytes(data, policy=email.policy.default)
        if not isinstance(message, EmailMessage) or not (
            _raw(message, "From").strip() or _raw(message, "Date").strip()
        ):
            raise UnprocessableDocumentError(because(ReasonCode.FILE_DAMAGED))
        return _read(message, data, 0)
    except UnprocessableDocumentError:
        raise
    except Exception:
        log.warning("a mail could not be read", exc_info=True)
        raise UnprocessableDocumentError(because(ReasonCode.FILE_DAMAGED)) from None


def _read(message: EmailMessage, source: bytes | Callable[[], bytes], depth: int) -> MailMessage:
    """`message`, attached `depth` levels deep."""
    html = _body(message, "html")
    text = _body(message, "plain")
    shown = _html_of(message)
    attachments: list[MailPart] = []
    pictures: list[MailPart] = []
    messages: list[MailMessage] = []
    for part in _leaves(message):
        kind = part.get_content_type()
        if kind == RFC822:
            inner = _attached(part)
            if inner is None:
                continue
            if depth < MAX_FORWARDS:
                messages.append(_read(inner, partial(_bytes, inner), depth + 1))
            else:
                attachments.append(MailPart(_filename(part), RFC822, _bytes(inner)))
            continue
        if _is_body(part, html, text):
            continue
        content_id = _content_id(part)
        disposition = part.get_content_disposition()
        payload = _payload(part)
        if payload is None:
            continue
        piece = MailPart(
            filename=_filename(part),
            media_type=kind,
            data=payload,
            content_id=content_id,
            inline=disposition == "inline" or (disposition is None and content_id is not None),
        )
        if content_id is not None and kind.startswith("image/"):
            pictures.append(piece)
        if disposition == "attachment" or (piece.filename and not _embedded(piece, shown)):
            attachments.append(piece)
    return MailMessage(
        sender=_addresses(message, "From"),
        to=_addresses(message, "To"),
        cc=_addresses(message, "Cc"),
        subject=_header(message, "Subject"),
        date=_date(message),
        message_id=_bare(_header(message, "Message-ID")) or None,
        html=None if html is None else html[1],
        text=None if text is None else text[1],
        attachments=tuple(attachments),
        pictures=tuple(pictures),
        messages=tuple(messages),
        source=source,
        importance=importance_of(
            {
                name: _header(message, name) or None
                for name in ("importance", "x-priority", "priority", "x-msmail-priority")
            }
        ),
    )


def _bytes(message: EmailMessage) -> bytes:
    try:
        return message.as_bytes(policy=_SMTP)
    except (LookupError, UnicodeError, ValueError):
        return message.as_bytes(policy=email.policy.compat32)


def _leaves(message: Message) -> Iterator[Message]:
    """The parts of `message` that are no container, an attached mail as one part: its own
    parts are its."""
    for part in message.get_payload() if message.is_multipart() else ():
        if not isinstance(part, Message):
            continue
        if part.get_content_type() == RFC822 or not part.is_multipart():
            yield part
        else:
            yield from _leaves(part)


def _body(message: EmailMessage, kind: str) -> tuple[Message, str] | None:
    """The part `get_body` takes for `kind` and its text; the inner mails' bodies are theirs."""
    part = message.get_body(preferencelist=(kind,))
    if part is None or part.get_content_type() != f"text/{kind}":
        return None
    content = _text(part)
    return None if content is None else (part, content)


def _html_of(message: EmailMessage) -> str:
    """The HTML of all the mail's own text parts, in lower case: Apple Mail splits its text
    around what it shows inline, so the part `get_body` takes need not hold every `cid:`."""
    return "\n".join(
        content.casefold()
        for part in _leaves(message)
        if part.get_content_type() == "text/html"
        and part.get_content_disposition() != "attachment"
        and (content := _text(part)) is not None
    )


def _embedded(piece: MailPart, html: str) -> bool:
    """Whether a part is shown inside the mail's text (`cid:` in its HTML): a logo, a picture of
    the signature. A part sent inline but shown nowhere by reference is an attachment, as Apple
    Mail sends a PDF or a photo (Content-Disposition `inline` with a file name; Tobi,
    06.11.2026)."""
    return (
        piece.inline
        and piece.content_id is not None
        and f"cid:{piece.content_id.casefold()}" in html
    )


def _is_body(part: Message, *bodies: tuple[Message, str] | None) -> bool:
    return any(body is not None and body[0] is part for body in bodies)


def _text(part: Message) -> str | None:
    try:
        content = part.get_content()  # type: ignore[attr-defined]
    except (LookupError, UnicodeError, ValueError):
        raw = part.get_payload(decode=True)
        if not isinstance(raw, bytes):
            return None
        content = raw.decode("utf-8", errors="replace")
    return content if isinstance(content, str) else None


def _payload(part: Message) -> bytes | None:
    raw = part.get_payload(decode=True)
    return raw if isinstance(raw, bytes) else None


def _attached(part: Message) -> EmailMessage | None:
    payload = part.get_payload()
    inner = payload[0] if isinstance(payload, list) and payload else payload
    return inner if isinstance(inner, EmailMessage) else None


def _filename(part: Message) -> str | None:
    try:
        name = part.get_filename()
    except (LookupError, UnicodeError, ValueError):
        return None
    return clean_filename(_SPACE.sub(" ", name)) or None if name else None


def _content_id(part: Message) -> str | None:
    value = part.get("Content-ID")
    return _bare(str(value)) or None if value else None


def _bare(value: str) -> str:
    return value.strip().removeprefix("<").removesuffix(">").strip()


def _raw(message: Message, name: str, *, listed: bool = False) -> str:
    """The raw value of the header `name` (its first line, as `Message.get` takes it), at most
    `MAX_RAW_HEADER` characters; `listed`: a list of addresses, all its lines joined by `, `
    (as `Message.get_all` takes them) and cut at the last comma before. Nothing parsed."""
    values = [str(value) for key, value in message.raw_items() if key.lower() == name.lower()]
    joined = ", ".join(values if listed else values[:1])
    if len(joined) <= MAX_RAW_HEADER:
        return joined
    cut = joined[:MAX_RAW_HEADER]
    return cut.rpartition(",")[0] if listed and "," in cut else cut


def _parsed(message: Message, name: str, *, listed: bool = False) -> str:
    """The header `name` decoded (encoded words), from its raw values (`_raw`); empty if it
    cannot be read."""
    raw = _raw(message, name, listed=listed)
    if not raw:
        return ""
    try:
        return str(email.policy.default.header_fetch_parse(name, raw))
    except (LookupError, UnicodeError, ValueError):
        return ""


def _header(message: EmailMessage, name: str) -> str:
    value = _parsed(message, name)
    return without_control(_SPACE.sub(" ", value)).strip()[:MAX_HEADER]


def _addresses(message: EmailMessage, name: str) -> tuple[Address, ...]:
    found = []
    for display, address in getaddresses([_parsed(message, name, listed=True)]):
        address = without_control(address).strip()
        if (address or display) and len(address) <= MAX_ADDRESS:
            name_shown = without_control(_SPACE.sub(" ", display)).strip()[:MAX_NAME]
            found.append(Address(name_shown, address))
    return tuple(found)


def _date(message: EmailMessage) -> datetime | None:
    value = _header(message, "Date")
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        return moment.astimezone(UTC)
    except (TypeError, ValueError, IndexError, OverflowError):
        # A date at the edge of the calendar (`31 Dec 9999 … -0100`) leaves it in UTC.
        return None
