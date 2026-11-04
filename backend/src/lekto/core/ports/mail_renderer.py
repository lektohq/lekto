"""Setting a mail (`.eml`) as a PDF: the archive of a mail and the source of its page images.

First adapter: WeasyPrint. The PDF starts with a head that says "E-Mail" and names sender,
recipients, date, subject, the attachments Lekto takes and those it cannot read ("Nicht
übernommen"; small images left out); then the mail's HTML part, or its plain text where it
has none. Nothing is loaded from the network or the file system: a picture comes
from the mail itself (`cid:`) or is left out.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RenderedMail:
    pages: int
    renderer: str  # name and version
    pdfa: bool


class MailRenderer(Protocol):
    async def render(self, mail: Path, target: Path) -> RenderedMail:
        """Write the mail `mail` as a PDF to `target`. UnprocessableDocumentError if it is no
        mail. Runs outside the event loop."""
        ...
