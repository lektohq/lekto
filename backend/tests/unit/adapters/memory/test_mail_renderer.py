"""The in-memory mail renderer passes the contract suite."""

import pytest

from lekto.adapters.outbound.memory import FakeMailRenderer
from lekto.core.ports.mail_renderer import MailRenderer
from tests.contracts.mail_renderer import MailRendererContract


class TestFakeMailRenderer(MailRendererContract):
    @pytest.fixture
    def renderer(self) -> MailRenderer:
        return FakeMailRenderer()
