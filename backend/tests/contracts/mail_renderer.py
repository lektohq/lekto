"""Contract suite for `MailRenderer`: a mail becomes a PDF, anything else is refused."""

from pathlib import Path

import pytest

from lekto.core.domain import media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.ports.mail_renderer import MailRenderer
from tests.mails import plain_mail, rich_mail


class MailRendererContract:
    @pytest.fixture
    def renderer(self) -> MailRenderer:
        raise NotImplementedError

    @pytest.mark.parametrize("data", [plain_mail(), rich_mail()], ids=["plain", "rich"])
    async def test_a_mail_becomes_a_pdf(
        self, renderer: MailRenderer, tmp_path: Path, data: bytes
    ) -> None:
        mail, target = tmp_path / "mail.eml", tmp_path / "mail.pdf"
        mail.write_bytes(data)
        rendered = await renderer.render(mail, target)
        assert rendered.pages >= 1
        assert rendered.renderer
        head = target.read_bytes()[: media_types.SNIFF_SIZE]
        assert media_types.detect(head) == media_types.PDF

    async def test_no_mail_is_refused(self, renderer: MailRenderer, tmp_path: Path) -> None:
        mail = tmp_path / "mail.eml"
        mail.write_bytes(b"%PDF-1.7\n%%EOF\n")
        with pytest.raises(UnprocessableDocumentError):
            await renderer.render(mail, tmp_path / "mail.pdf")
