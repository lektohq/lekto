"""Reading a mail: what it says about itself, its text, attachments, pictures and the mails
attached to it; and telling a mail from other files by its first bytes."""

from datetime import UTC, datetime

import pytest

from lekto.core.domain import media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.mail_intake import letters
from lekto.core.domain.mail_message import Address, read_mail
from tests.mails import PDF, PNG, apple_mail, plain_mail, rich_mail


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
