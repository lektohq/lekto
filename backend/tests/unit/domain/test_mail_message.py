"""Reading a mail: what it says about itself, its text, attachments, pictures and the mails
attached to it; and telling a mail from other files by its first bytes."""

import time
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from lekto.core.domain import mail_message, media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.mail_intake import letters
from lekto.core.domain.mail_message import MAX_FORWARDS, Address, read_mail
from lekto.core.domain.validation import MAX_NAME
from tests.mails import (
    PDF,
    PNG,
    apple_mail,
    named_attachments_mail,
    nested_mail,
    plain_mail,
    rich_mail,
)


def test_reads_what_a_mail_says_about_itself() -> None:
    mail = read_mail(rich_mail())
    assert mail.sender == (Address("Stadtwerke Musterstadt", "rechnung@stadtwerke.example"),)
    assert [address.address for address in mail.to] == ["anna@example.test", "ben@example.test"]
    assert mail.cc[0].shown == "Buchhaltung <buchhaltung@example.test>"
    assert mail.subject == "Ihre Rechnung über 123,45 €"
    assert mail.date == datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
    assert mail.message_id == "rechnung-4711@stadtwerke.example"


def test_reads_text_html_attachments_pictures_and_attached_mails() -> None:
    mail = read_mail(rich_mail())
    assert mail.text is not None and "123,45 €" in mail.text
    assert mail.html is not None and "<b>Anna</b>" in mail.html
    assert [(part.filename, part.media_type, part.data) for part in mail.attachments] == [
        ("Rechnung 4711.pdf", "application/pdf", PDF)
    ]
    assert [(part.content_id, part.data) for part in mail.pictures] == [("logo@stadtwerke", PNG)]
    (inner,) = mail.messages
    assert (inner.subject, inner.text) == ("Vertrag", "Der Vertrag.\n")
    assert inner.attachments == ()


def test_what_apple_mail_sends_inline_with_a_file_name_is_an_attachment() -> None:
    """Apple Mail sends a PDF or a photo `inline` with a file name; it is an attachment unless
    the HTML embeds it by `cid:` (in any of its HTML parts, regardless of case)."""
    mail = read_mail(apple_mail())
    assert [(part.filename, part.media_type) for part in mail.attachments] == [
        ("Rechnung.pdf", "application/pdf"),
        ("Foto.png", "image/png"),
    ]
    assert mail.attachments[0].data == PDF
    assert [part.content_id for part in mail.pictures] == ["Logo@Example"]
    (letter,) = letters(mail)
    assert [part.filename for part in letter.taken] == ["Rechnung.pdf", "Foto.png"]


def test_a_plain_mail_has_its_text_only() -> None:
    mail = read_mail(plain_mail())
    assert (mail.html, mail.text, mail.attachments, mail.messages) == (
        None,
        "Hallo Anna,\n\nanbei.\n",
        (),
        (),
    )


def test_a_part_in_an_unknown_charset_is_read_with_replacements() -> None:
    data = (
        b"From: a@example.test\r\nDate: Tue, 04 Nov 2026 10:00:00 +0100\r\nSubject: x\r\n"
        b"Content-Type: text/plain; charset=no-such-charset\r\n\r\nGr\xfc\xdfe\r\n"
    )
    mail = read_mail(data)
    assert mail.text is not None and mail.text.startswith("Gr")


def test_no_mail_is_refused() -> None:
    with pytest.raises(UnprocessableDocumentError):
        read_mail(b"just some text\n")


@pytest.mark.parametrize(
    "head",
    [
        plain_mail(),
        rich_mail(),
        b"Delivered-To: anna@example.test\r\nReceived: by 2002:a05 with SMTP id x;\r\n"
        b"        Tue, 4 Nov 2026 01:00:00 -0800 (PST)\r\nX-Google: y\r\n",
        b"Return-Path: <a@example.test>\nFrom: a@example.test\nSubject: Hallo",
    ],
    ids=["plain", "rich", "gmail", "return-path"],
)
def test_a_mail_is_told_by_its_header_lines(head: bytes) -> None:
    assert media_types.detect(head[: media_types.SNIFF_SIZE]) == media_types.EML


@pytest.mark.parametrize(
    "head",
    [
        b"Note: this is a text file\nwith some lines\n",
        b"Subject: only one header\n\nand a body",
        b"Hello: world\nFoo: bar\n\nbody",
        b"\n\nFrom: a@example.test\nDate: x\n",
        PDF,
        PNG,
    ],
    ids=["text", "one-header", "unknown-headers", "blank-first", "pdf", "png"],
)
def test_other_files_are_no_mail(head: bytes) -> None:
    assert media_types.detect(head) != media_types.EML


def test_names_and_header_values_lose_paths_and_control_characters() -> None:
    raw = named_attachments_mail(
        "../../etc/a\x00b\x07.pdf", "b" * 3000 + ".pdf", subject="=?utf-8?q?Rechnung=00_1?="
    )
    mail = read_mail(raw)
    assert [part.filename for part in mail.attachments] == ["ab.pdf", "b" * 255]
    assert mail.subject == "Rechnung 1"


def test_a_date_at_the_edge_of_the_calendar_is_no_date() -> None:
    raw = plain_mail().replace(
        b"Date: Wed, 04 Nov 2026 10:00:00 +0100", b"Date: Fri, 31 Dec 9999 23:59:59 -0100"
    )
    assert read_mail(raw).date is None


def test_a_mail_that_breaks_reading_is_a_damaged_file() -> None:
    """Anything that fails while reading a mail (here: mails attached too deep for the standard
    library) is a damaged file, which the mail intake records and goes past."""
    with pytest.raises(UnprocessableDocumentError):
        read_mail(nested_mail(150))


def test_a_mail_attached_deeper_than_five_levels_stays_an_attachment() -> None:
    """Five levels of attached mails are read; the mail attached to the fifth stays its
    attachment (`.eml`): one letter of the fifth with five forwarders, not a letter more for
    each five levels below (DB-01, SB-02)."""
    mail = read_mail(nested_mail(8))
    (letter,) = letters(mail)
    assert letter.message.subject == "Weitergeleitet 2"
    assert len(letter.forwarded_by) == MAX_FORWARDS
    assert letter.message.messages == ()
    (attached,) = letter.taken
    assert attached.media_type == media_types.EML
    assert read_mail(attached.data).subject == "Weitergeleitet 1"


def test_an_attached_mail_is_written_as_a_file_only_when_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each level would write all below it again: a hundred levels of 16 MB took 91 s and
    1.6 GB. Only the mail attached below the last level read is written while reading."""
    writing = mail_message._bytes
    written: list[str] = []

    def write(message: EmailMessage) -> bytes:
        written.append(str(message["Subject"]))
        return writing(message)

    monkeypatch.setattr(mail_message, "_bytes", write)
    deep = read_mail(nested_mail(100))
    assert written == ["Weitergeleitet 93"]  # attached to the fifth level
    assert deep.raw == nested_mail(100)  # the mail as received
    written.clear()
    mail = read_mail(nested_mail(3))
    assert written == []
    inner = mail.messages[0].messages[0].messages[0]
    assert read_mail(inner.raw).subject == inner.subject == "Innen"
    assert inner.raw is inner.raw
    assert written == ["Innen"]  # once, when asked for


def addressed(to: str, sender: str = "Jane Doe <jane@example.org>", *, more: str = "") -> bytes:
    """A plain mail from `sender` to `to`, with `more` header lines."""
    head = f"From: {sender}\r\nTo: {to}\r\n{more}Subject: Hallo\r\n"
    return (head + "Date: Mon, 16 Nov 2026 10:00:00 +0000\r\n\r\nbody\r\n").encode()


def many(count: int, start: int = 0) -> str:
    return ", ".join(
        f"=?utf-8?q?M=C3=BCller_{number}?= <user{number}@example.org>"
        for number in range(start, start + count)
    )


def test_a_long_list_of_recipients_is_read_as_far_as_the_limit_in_time() -> None:
    """The standard library parses a list of addresses in a time growing with its square:
    16 000 recipients took 19 s, also in a mail attached to one."""
    head = addressed(many(16_000))
    attached = addressed("John Doe <john@example.org>").replace(
        b"\r\n\r\nbody\r\n",
        b'\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary="b"\r\n\r\n'
        b"--b\r\nContent-Type: text/plain\r\n\r\nsee below\r\n"
        b"--b\r\nContent-Type: message/rfc822\r\n\r\n" + head + b"\r\n--b--\r\n",
    )
    started = time.perf_counter()
    mail, outer = read_mail(head), read_mail(attached)
    assert time.perf_counter() - started < 1
    (inner,) = outer.messages
    assert inner.to == mail.to
    assert 100 < len(mail.to) < 16_000
    assert mail.to[0] == Address("Müller 0", "user0@example.org")
    last = len(mail.to) - 1  # cut at a comma: no half address
    assert mail.to[-1] == Address(f"Müller {last}", f"user{last}@example.org")


def test_the_lines_of_a_list_share_the_limit_other_headers_keep_their_first() -> None:
    raw = addressed(many(150), more=f"To: {many(150, start=150)}\r\nSubject: Zweiter\r\n")
    mail = read_mail(raw)
    assert mail.to[150] == Address("Müller 150", "user150@example.org")
    assert 150 < len(mail.to) < 300  # 15 000 characters in two lines, cut at `MAX_RAW_HEADER`
    assert mail.subject == "Zweiter"  # the first Subject line (the other follows it)


def test_a_name_is_cut_and_an_address_too_long_left_out() -> None:
    raw = addressed(
        f"{'x' * 300}@example.org, John Doe <john@example.org>",
        sender=f'"{"N" * 5000}" <jane@example.org>',
    )
    mail = read_mail(raw)
    assert mail.sender == (Address("N" * MAX_NAME, "jane@example.org"),)
    assert mail.to == (Address("John Doe", "john@example.org"),)
