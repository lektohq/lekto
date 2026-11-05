"""Mails for the tests, built with `email` of the standard library."""

import hashlib
from email.message import EmailMessage

from lekto.core.domain.mail import MailLogin, MailSecurity

LOGIN = MailLogin(
    host="imap.example.test",
    port=993,
    security=MailSecurity.TLS,
    username="household@example.test",
    password="right",
)
"""The account the tests sign in to, on the memory mail server."""

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
PDF = b"%PDF-1.7\n% a test attachment\n%%EOF\n"


def plain_mail(
    subject: str = "Ihre Rechnung Oktober", text: str = "Hallo Anna,\n\nanbei."
) -> bytes:
    message = EmailMessage()
    message["From"] = "Stadtwerke Musterstadt <rechnung@stadtwerke.example>"
    message["To"] = "Anna Beispiel <anna@example.test>"
    message["Date"] = "Wed, 04 Nov 2026 10:00:00 +0100"
    message["Message-ID"] = (
        f"<{hashlib.sha256(subject.encode()).hexdigest()[:16]}@stadtwerke.example>"
    )
    message["Subject"] = subject
    message.set_content(text)
    return bytes(message)


def rich_mail(html: str | None = None) -> bytes:
    """Text and HTML with a picture by `cid:`, a PDF attached, and a forwarded mail."""
    message = EmailMessage()
    message["From"] = "Stadtwerke Musterstadt <rechnung@stadtwerke.example>"
    message["To"] = "Anna Beispiel <anna@example.test>, ben@example.test"
    message["Cc"] = "Buchhaltung <buchhaltung@example.test>"
    message["Date"] = "Wed, 04 Nov 2026 10:00:00 +0100"
    message["Message-ID"] = "<rechnung-4711@stadtwerke.example>"
    message["Subject"] = "=?utf-8?q?Ihre_Rechnung_=C3=BCber_123=2C45_=E2=82=AC?="
    message.set_content("Hallo Anna,\n\nanbei die Rechnung über 123,45 €.\n")
    message.add_alternative(
        html
        or (
            "<html><head><style>p { color: #333 }</style></head><body>"
            "<p>Hallo <b>Anna</b>,</p><p>anbei die Rechnung über 123,45 €.</p>"
            '<img src="cid:logo@stadtwerke"></body></html>'
        ),
        subtype="html",
    )
    alternative = message.get_payload()[1]  # type: ignore[index]
    assert isinstance(alternative, EmailMessage)
    alternative.add_related(PNG, maintype="image", subtype="png", cid="<logo@stadtwerke>")
    message.add_attachment(PDF, maintype="application", subtype="pdf", filename="Rechnung 4711.pdf")
    inner = EmailMessage()
    inner["From"] = "ben@example.test"
    inner["Subject"] = "Vertrag"
    inner["Date"] = "Mon, 03 Nov 2026 08:00:00 +0000"
    inner.set_content("Der Vertrag.")
    message.add_attachment(inner)
    return bytes(message)
