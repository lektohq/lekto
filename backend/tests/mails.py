"""Mails for the tests, built with `email` of the standard library."""

import base64
import hashlib
from email.message import EmailMessage

from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.mail_intake import SMALL_IMAGE

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


def apple_mail() -> bytes:
    """As Apple Mail sends a mail with a PDF (Tobi, 06.11.2026): its HTML split around what it
    shows inline, the PDF and a photo `inline` with a file name, and a logo the second part of
    the HTML embeds by `cid:`."""
    pdf = base64.b64encode(PDF).decode()
    png = base64.b64encode(PNG).decode()
    photo = base64.b64encode(PNG + bytes(SMALL_IMAGE)).decode()  # larger than a logo
    return (
        "From: Anna Beispiel <anna@example.test>\r\n"
        "To: dms@example.test\r\n"
        "Subject: Ein Test mit Anhang\r\n"
        "Date: Fri, 06 Nov 2026 09:27:00 +0100\r\n"
        "Message-ID: <apple-1@example.test>\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/alternative; boundary="alt"\r\n'
        "\r\n"
        "--alt\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Hallo,\r\nanbei die Rechnung.\r\n"
        "--alt\r\n"
        'Content-Type: multipart/mixed; boundary="mix"\r\n'
        "\r\n"
        "--mix\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        "<html><body><p>Hallo,</p><p>anbei die Rechnung.</p></body></html>\r\n"
        "--mix\r\n"
        'Content-Type: application/pdf; name="Rechnung.pdf"\r\n'
        'Content-Disposition: inline; filename="Rechnung.pdf"\r\n'
        "Content-Transfer-Encoding: base64\r\n"
        "\r\n"
        f"{pdf}\r\n"
        "--mix\r\n"
        'Content-Type: image/png; name="Foto.png"\r\n'
        'Content-Disposition: inline; filename="Foto.png"\r\n'
        "Content-Transfer-Encoding: base64\r\n"
        "\r\n"
        f"{photo}\r\n"
        "--mix\r\n"
        'Content-Type: image/png; name="Logo.png"\r\n'
        'Content-Disposition: inline; filename="Logo.png"\r\n'
        "Content-ID: <Logo@Example>\r\n"
        "Content-Transfer-Encoding: base64\r\n"
        "\r\n"
        f"{png}\r\n"
        "--mix\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        "\r\n"
        '<html><body><p>Gruß</p><img src="cid:logo@example"></body></html>\r\n'
        "--mix--\r\n"
        "--alt--\r\n"
    ).encode()
