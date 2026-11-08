"""The WeasyPrint adapter passes the contract suite and sets what a mail holds: the head with
"E-Mail", sender, recipients, date, subject and attachments, then the HTML or the text. It
loads nothing from the network or the file system."""

from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path

import pypdfium2
import pytest

from lekto.adapters.outbound.weasyprint import WeasyPrintMailRenderer
from lekto.core.ports.mail_renderer import MailRenderer
from tests.builders import DEFAULT_SETTINGS
from tests.contracts.mail_renderer import MailRendererContract
from tests.mails import PDF, PNG, plain_mail, rich_mail
from tests.webhook_receiver import LocalReceiver


class TestWeasyPrintMailRenderer(MailRendererContract):
    @pytest.fixture
    def renderer(self) -> MailRenderer:
        return WeasyPrintMailRenderer("de", memory=int(DEFAULT_SETTINGS.child_max_memory))


def _text(pdf: Path) -> str:
    document = pypdfium2.PdfDocument(str(pdf))
    try:
        return "\n".join(page.get_textpage().get_text_range() for page in document)
    finally:
        document.close()


async def _render(data: bytes, tmp_path: Path, locale: str = "de") -> str:
    mail, target = tmp_path / "mail.eml", tmp_path / "mail.pdf"
    mail.write_bytes(data)
    await WeasyPrintMailRenderer(locale).render(mail, target)
    return _text(target)


async def test_the_head_and_the_html(tmp_path: Path) -> None:
    text = await _render(rich_mail(), tmp_path)
    for expected in (
        "E-MAIL",
        "Ihre Rechnung über 123,45 €",
        "Von Stadtwerke Musterstadt <rechnung@stadtwerke.example>",
        "An Anna Beispiel <anna@example.test>, ben@example.test",
        "Kopie Buchhaltung <buchhaltung@example.test>",
        "Datum 04.11.2026, 09:00 UTC",
        "Anhänge Rechnung 4711.pdf",
        "anbei die Rechnung über 123,45 €.",
    ):
        assert expected in text


async def test_a_plain_mail_in_english(tmp_path: Path) -> None:
    text = await _render(plain_mail(text="Line one\n\n> quoted line"), tmp_path, "en")
    assert "From Stadtwerke Musterstadt" in text
    assert "Date 2026-11-04 09:00 UTC" in text
    assert "> quoted line" in text


async def test_nothing_is_loaded_from_outside(tmp_path: Path) -> None:
    async with LocalReceiver() as receiver:
        html = (
            "<html><body><p>Tracked</p>"
            f'<img src="{receiver.url}/pixel.png">'
            f'<link rel="stylesheet" href="{receiver.url}/style.css">'
            '<img src="file:///etc/hostname"></body></html>'
        )
        text = await _render(rich_mail(html), tmp_path)
        assert "Tracked" in text
        assert receiver.hits("/pixel.png") == 0
        assert receiver.hits("/style.css") == 0


async def test_what_is_not_taken_is_named(tmp_path: Path) -> None:
    message = EmailMessage()
    message["From"] = "a@example.test"
    message["Date"] = "Wed, 04 Nov 2026 10:00:00 +0100"
    message["Subject"] = "Unterlagen"
    message.set_content("Anbei.")
    message.add_attachment(PDF, maintype="application", subtype="pdf", filename="Vertrag.pdf")
    message.add_attachment(b"PK\x03\x04", maintype="application", subtype="zip", filename="x.zip")
    message.add_attachment(PNG, maintype="image", subtype="png", filename="logo.png")
    text = await _render(bytes(message), tmp_path)
    assert "Anhänge Vertrag.pdf" in text
    assert "Nicht übernommen x.zip" in text
    assert "logo.png" not in text


async def test_a_mail_that_takes_too_long_to_set_is_stopped(tmp_path: Path) -> None:
    """The child process is killed after the time limit: a mail's HTML comes from anyone."""
    mail, target = tmp_path / "mail.eml", tmp_path / "mail.pdf"
    mail.write_bytes(plain_mail())
    renderer = WeasyPrintMailRenderer("de", timeout=timedelta(milliseconds=20))
    with pytest.raises(TimeoutError):
        await renderer.render(mail, target)
    assert not target.exists()
