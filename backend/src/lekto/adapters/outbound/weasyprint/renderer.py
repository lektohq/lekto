"""The WeasyPrint adapter of `MailRenderer`."""

import html
import json
import re
import sys
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any

from lekto.adapters.outbound.system import run_process
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.mail_intake import Letter
from lekto.core.domain.mail_message import MailMessage, MailPart, address_line, read_mail
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.mail_renderer import RenderedMail

CHILD = "lekto.adapters.outbound.weasyprint"
"""The module the child process runs (`__main__`)."""
NO_MAIL = 3
"""Exit code of the child process when the file is no mail."""
DEFAULT_TIMEOUT = timedelta(minutes=2)

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
        "left": "Nicht übernommen",
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
        "left": "Not taken",
        "none": "(no subject)",
        "moment": "%Y-%m-%d %H:%M UTC",
    },
}

_BASE = """
@page { size: A4; margin: 16mm 15mm 18mm; }
body { font: 10pt/1.45 "Nimbus Sans", "DejaVu Sans", sans-serif; color: #1b1a17; }
"""
"""The page and a plain font, before the mail's own styles: they may change it."""

_STYLE = """
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
    """Sets each mail in a child process (`python -m lekto.adapters.outbound.weasyprint`) with a
    time limit: a mail's HTML comes from anyone, and WeasyPrint has no limit of its own, so a
    page built to take forever would hold the worker. `locale`: the language of the head
    (`de`, else English); `timeout`: TimeoutError after it, the child killed."""

    def __init__(self, locale: str = "de", timeout: timedelta = DEFAULT_TIMEOUT) -> None:
        self._locale = locale
        self._timeout = timeout

    async def render(self, mail: Path, target: Path) -> RenderedMail:
        completed = await run_process(
            [sys.executable, "-m", CHILD, self._locale, str(mail), str(target)],
            timeout=self._timeout,
        )
        if completed.returncode == NO_MAIL:
            raise UnprocessableDocumentError(because(ReasonCode.FILE_DAMAGED))
        if completed.returncode != 0:
            raise RuntimeError(
                f"setting the mail failed with exit code {completed.returncode}: "
                f"{_last_line(completed.stderr)}"
            )
        try:
            data = json.loads(completed.stdout)
            return RenderedMail(
                pages=int(data["pages"]), renderer=str(data["renderer"]), pdfa=bool(data["pdfa"])
            )
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("setting the mail gave no usable answer") from None


def set_mail(mail: Path, target: Path, locale: str) -> RenderedMail:
    """Write the mail `mail` as a PDF to `target`, in this process: what the child of
    `WeasyPrintMailRenderer.render` does. UnprocessableDocumentError if it is no mail."""
    # Imported here: WeasyPrint loads Pango as it is imported, which only the child needs.
    import weasyprint

    message = read_mail(mail.read_bytes())
    page = weasyprint.HTML(string=page_of(message, locale), url_fetcher=_fetcher(message.pictures))
    document = page.render()
    document.write_pdf(target, pdf_variant=PDF_VARIANT)
    return RenderedMail(
        pages=len(document.pages), renderer=f"weasyprint {version('weasyprint')}", pdfa=True
    )


def page_of(message: MailMessage, locale: str) -> str:
    """The HTML the PDF is set from, its head in `locale` (`de`, else English)."""
    labels = _LABELS.get(locale.split("-")[0].lower(), _LABELS["en"])
    styles, body = _content(message)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<style>{_BASE}</style>{styles}<style>{_STYLE}</style></head><body>"
        f"{_head(message, labels)}{body}</body></html>"
    )


def _head(message: MailMessage, labels: dict[str, str]) -> str:
    letter = Letter(message)
    rows = [
        ("from", address_line(message.sender)),
        ("to", address_line(message.to)),
        ("cc", address_line(message.cc)),
        ("date", "" if message.date is None else message.date.strftime(labels["moment"])),
        ("attachments", ", ".join(_names(letter.taken))),
        ("left", ", ".join(_names(letter.left))),
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


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _content(message: MailMessage) -> tuple[str, str]:
    """The mail's own styles and body: of its HTML, else its text."""
    if message.html is not None:
        source = _SCRIPT.sub("", message.html)
        styles = "".join(_STYLE_BLOCK.findall(source))
        found = _BODY.search(source)
        body = found[1] if found else _HEAD.sub("", source)
        return styles, f'<div class="lekto-mail">{body}</div>'
    return "", f'<pre class="lekto-text">{html.escape(message.text or "")}</pre>'


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
