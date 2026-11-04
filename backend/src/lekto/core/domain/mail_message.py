"""A mail as Lekto reads it (`.eml`, RFC 5322 with MIME), with `email` of the standard library.

What a mail says about itself (sender, recipients, date, subject, Message-ID), its text (the HTML
part and the plain one, as far as there are), its attachments, the pictures its HTML shows by
`cid:`, and the mails attached to it. A part that cannot be decoded is read with replacement
characters rather than failing the mail.
"""

import email
import email.policy
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage, Message
from email.utils import getaddresses, parsedate_to_datetime

from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because

RFC822 = "message/rfc822"
MAX_HEADER = 1000
"""Characters of a header value kept (a subject, a list of recipients)."""

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


@dataclass(frozen=True)
class MailPart:
    """An attachment, or a picture of the HTML (`content_id`, without angle brackets)."""

    filename: str | None
    media_type: str
    data: bytes
    content_id: str | None = None
    inline: bool = False


@dataclass(frozen=True, kw_only=True)
class MailMessage:
    sender: tuple[Address, ...]
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    reply_to: tuple[Address, ...]
    subject: str
    date: datetime | None  # UTC
    message_id: str | None  # without angle brackets
    html: str | None
    text: str | None
    attachments: tuple[MailPart, ...]
    """Parts given as attachments, attached mails aside (`messages`)."""
    pictures: tuple[MailPart, ...]
    """Parts the HTML can show by `cid:`."""
    messages: tuple["MailMessage", ...]
    """Mails attached to this one (a forward as attachment)."""
    raw: bytes = field(repr=False, default=b"")
    """The mail as a file (`.eml`): as received, or an attached one as it stands in it."""


def read_mail(data: bytes) -> MailMessage:
    """The mail `data`; UnprocessableDocumentError if it has no header of a mail at all."""
    message = email.message_from_bytes(data, policy=email.policy.default)
    if not isinstance(message, EmailMessage) or not (message["From"] or message["Date"]):
        raise UnprocessableDocumentError(because(ReasonCode.FILE_DAMAGED))
    return _read(message, data)


def _read(message: EmailMessage, raw: bytes) -> MailMessage:
    html = _body(message, "html")
    text = _body(message, "plain")
    attachments: list[MailPart] = []
    pictures: list[MailPart] = []
    messages: list[MailMessage] = []
    for part in _leaves(message):
        kind = part.get_content_type()
        if kind == RFC822:
            inner = _attached(part)
            if inner is not None:
                messages.append(_read(inner, _bytes(inner)))
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
        if disposition == "attachment" or (piece.filename and not piece.inline):
            attachments.append(piece)
    return MailMessage(
        sender=_addresses(message, "From"),
        to=_addresses(message, "To"),
        cc=_addresses(message, "Cc"),
        reply_to=_addresses(message, "Reply-To"),
        subject=_header(message, "Subject"),
        date=_date(message),
        message_id=_bare(_header(message, "Message-ID")) or None,
        html=None if html is None else html[1],
        text=None if text is None else text[1],
        attachments=tuple(attachments),
        pictures=tuple(pictures),
        messages=tuple(messages),
        raw=raw,
    )


def _bytes(message: EmailMessage) -> bytes:
    try:
        return message.as_bytes(policy=email.policy.SMTP)
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
    return _SPACE.sub(" ", name).strip() or None if name else None


def _content_id(part: Message) -> str | None:
    value = part.get("Content-ID")
    return _bare(str(value)) or None if value else None


def _bare(value: str) -> str:
    return value.strip().removeprefix("<").removesuffix(">").strip()


def _header(message: EmailMessage, name: str) -> str:
    try:
        value = message.get(name)
    except (LookupError, UnicodeError, ValueError):
        return ""
    return _SPACE.sub(" ", str(value)).strip()[:MAX_HEADER] if value is not None else ""


def _addresses(message: EmailMessage, name: str) -> tuple[Address, ...]:
    try:
        values = message.get_all(name) or []
    except (LookupError, UnicodeError, ValueError):
        return ()
    found = []
    for display, address in getaddresses([str(value) for value in values]):
        if address or display:
            found.append(Address(_SPACE.sub(" ", display).strip(), address.strip()))
    return tuple(found)


def _date(message: EmailMessage) -> datetime | None:
    value = _header(message, "Date")
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)
