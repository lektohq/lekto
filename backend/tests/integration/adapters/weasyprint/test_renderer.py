"""The WeasyPrint adapter passes the contract suite and sets what a mail holds: the head with
"E-Mail", sender, recipients, date, subject and attachments, then the HTML or the text. It
loads nothing from the network or the file system."""

from pathlib import Path

import pypdfium2
import pytest

from lekto.adapters.outbound.weasyprint import WeasyPrintMailRenderer
from lekto.core.ports.mail_renderer import MailRenderer
from tests.contracts.mail_renderer import MailRendererContract
from tests.mails import plain_mail, rich_mail
from tests.webhook_receiver import LocalReceiver


class TestWeasyPrintMailRenderer(MailRendererContract):
    @pytest.fixture
    def renderer(self) -> MailRenderer:
        return WeasyPrintMailRenderer("de")


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
