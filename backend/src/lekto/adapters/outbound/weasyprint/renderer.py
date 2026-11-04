"""The WeasyPrint adapter of `MailRenderer`."""

import asyncio
import html
import re
from importlib.metadata import version
from pathlib import Path
from typing import Any

from lekto.core.domain.mail_message import Address, MailMessage, MailPart, read_mail
from lekto.core.ports.mail_renderer import RenderedMail

PDF_VARIANT = "pdf/a-3b"
"""PDF/A-3b: an archive like the others (PDF/A-2b and later allow what WeasyPrint writes)."""

_LABELS = {
    "de": {
        "kind": "E-Mail",
        "from": "Von",
        "to": "An",
        "cc": "Kopie",
        "date": "Datum",
        "subject": "Betreff",
        "attachments": "Anhänge",
        "none": "(ohne Betreff)",
        "moment": "%d.%m.%Y, %H:%M UTC",
    },
    "en": {
        "kind": "E-mail",
        "from": "From",
        "to": "To",
        "cc": "Cc",
        "date": "Date",
        "subject": "Subject",
        "attachments": "Attachments",
        "none": "(no subject)",
        "moment": "%Y-%m-%d %H:%M UTC",
    },
}

_STYLE = """
@page { size: A4; margin: 16mm 15mm 18mm; }
.lekto-head { font: 9.5pt/1.4 "Nimbus Sans", "DejaVu Sans", sans-serif !important;
  color: #1b1a17 !important; background: #fff !important; margin: 0 0 6mm !important;
  padding: 0 0 3mm !important; border-bottom: 0.6pt solid #b9b5ad !important; }
.lekto-head .lekto-kind { font-size: 8pt !important; letter-spacing: 0.06em;
  color: #5f5c55 !important; text-transform: uppercase; margin: 0 0 1.5mm !important; }
.lekto-head .lekto-subject { font-size: 13pt !important; font-weight: 600 !important;
  margin: 0 0 2mm !important; }
.lekto-head .lekto-row { margin: 0 !important; padding: 0 !important; }
.lekto-head .lekto-label { display: inline-block; min-width: 18mm; color: #5f5c55 !important; }
.lekto-text { font: 10pt/1.45 "Nimbus Sans", "DejaVu Sans", sans-serif; white-space: pre-wrap;
  overflow-wrap: anywhere; margin: 0; }
img { max-width: 100%; }
"""

_STYLE_BLOCK = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_BODY = re.compile(r"<body\b[^>]*>(.*?)(?:</body>|$)", re.IGNORECASE | re.DOTALL)
_HEAD = re.compile(r"<head\b[^>]*>.*?</head>", re.IGNORECASE | re.DOTALL)
_SCRIPT = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)


class WeasyPrintMailRenderer:
    """`locale`: the language of the head (`de`, else English)."""

    def __init__(self, locale: str = "de") -> None:
        self._labels = _LABELS.get(locale.split("-")[0].lower(), _LABELS["en"])

    async def render(self, mail: Path, target: Path) -> RenderedMail:
        return await asyncio.to_thread(self._render, mail, target)

    def _render(self, mail: Path, target: Path) -> RenderedMail:
        # Imported here: WeasyPrint loads Pango as it is imported, which only rendering needs.
        import weasyprint

        message = read_mail(mail.read_bytes())
        page = weasyprint.HTML(string=self.page(message), url_fetcher=_fetcher(message.pictures))
        document = page.render()
        document.write_pdf(target, pdf_variant=PDF_VARIANT)
        return RenderedMail(
            pages=len(document.pages),
            renderer=f"weasyprint {version('weasyprint')}",
            pdfa=True,
        )

    def page(self, message: MailMessage) -> str:
        """The HTML the PDF is set from."""
        styles, body = _content(message)
        return (
            '<!doctype html><html><head><meta charset="utf-8">'
            f"{styles}<style>{_STYLE}</style></head><body>"
            f"{self._head(message)}{body}</body></html>"
        )

    def _head(self, message: MailMessage) -> str:
        labels = self._labels
        rows = [
            ("from", _people(message.sender)),
            ("to", _people(message.to)),
            ("cc", _people(message.cc)),
            ("date", "" if message.date is None else message.date.strftime(labels["moment"])),
            ("attachments", ", ".join(_names(message.attachments))),
        ]
        lines = "".join(
            f'<p class="lekto-row"><span class="lekto-label">{labels[key]}</span> '
            f"{html.escape(value)}</p>"
            for key, value in rows
            if value
        )
        subject = message.subject or labels["none"]
        return (
            f'<header class="lekto-head"><p class="lekto-kind">{labels["kind"]}</p>'
            f'<p class="lekto-subject">{html.escape(subject)}</p>{lines}</header>'
        )


def _content(message: MailMessage) -> tuple[str, str]:
    """The mail's own styles and body: of its HTML, else its text."""
    if message.html is not None:
        source = _SCRIPT.sub("", message.html)
        styles = "".join(_STYLE_BLOCK.findall(source))
        found = _BODY.search(source)
        body = found[1] if found else _HEAD.sub("", source)
        return styles, f'<div class="lekto-mail">{body}</div>'
    return "", f'<pre class="lekto-text">{html.escape(message.text or "")}</pre>'


def _people(addresses: tuple[Address, ...]) -> str:
    return ", ".join(address.shown for address in addresses)


def _names(parts: tuple[MailPart, ...]) -> list[str]:
    return [part.filename for part in parts if part.filename]


def _fetcher(pictures: tuple[MailPart, ...]) -> Any:
    """A fetcher of the pictures of the mail by `cid:` and `data:` URLs; anything else (the
    network, files) is refused, and WeasyPrint leaves it out."""
    from weasyprint.urls import URLFetcher, URLFetcherResponse

    found = {part.content_id: part for part in pictures if part.content_id}

    class MailFetcher(URLFetcher):  # type: ignore[misc]
        def fetch(self, url: str, headers: Any = None) -> Any:
            if url.lower().startswith("cid:"):
                part = found.get(url[4:].strip("<>"))
                if part is None:
                    raise ValueError("no such picture in the mail")
                return URLFetcherResponse(
                    url, body=part.data, headers={"Content-Type": part.media_type}
                )
            if url.lower().startswith("data:"):
                return super().fetch(url, headers)
            raise ValueError("only pictures of the mail itself are shown")

    return MailFetcher(allowed_protocols=("data", "cid"))
