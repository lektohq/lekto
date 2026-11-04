"""Contract suite for `MailServer`. The adapter test provides a `world`: a server where it can
make a new account for a test, and an address where nobody listens."""

from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

import pytest

from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.reasons import ReasonCode
from lekto.core.ports.mail_server import MailServer, MailServerError


class MailWorld(Protocol):
    def account(self, folders: Sequence[str] = (), *, password: str = "secret") -> MailLogin:
        """A new account with `INBOX` and `folders`, on a server without TLS."""
        ...

    def unreachable(self) -> MailLogin:
        """A login for an address where nobody listens."""
        ...


class MailServerContract:
    @pytest.fixture
    def server(self) -> MailServer:
        raise NotImplementedError

    @pytest.fixture
    def world(self) -> MailWorld:
        raise NotImplementedError

    async def test_lists_the_folders_inbox_first(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.account(["Rechnungen", "Belege & Co", "Bestätigungen"])
        assert await server.folders(login) == (
            "INBOX",
            "Belege & Co",
            "Bestätigungen",
            "Rechnungen",
        )

    async def test_a_new_account_has_its_inbox(self, server: MailServer, world: MailWorld) -> None:
        assert await server.folders(world.account()) == ("INBOX",)

    async def test_a_password_beyond_ascii(self, server: MailServer, world: MailWorld) -> None:
        login = world.account(password="Grüße-1")
        assert await server.folders(login) == ("INBOX",)

    async def test_a_wrong_password_is_refused(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), password="wrong")
        with pytest.raises(MailServerError) as caught:
            await server.folders(login)
        assert caught.value.reason.code is ReasonCode.MAIL_LOGIN_FAILED

    async def test_an_unknown_user_is_refused(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), username="nobody-here")
        with pytest.raises(MailServerError) as caught:
            await server.folders(login)
        assert caught.value.reason.code is ReasonCode.MAIL_LOGIN_FAILED

    async def test_an_address_where_nobody_listens(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.unreachable()
        with pytest.raises(MailServerError) as caught:
            await server.folders(login)
        assert caught.value.reason.code is ReasonCode.MAIL_UNREACHABLE
        assert caught.value.reason.params == {"host": login.host}

    async def test_tls_with_a_server_without_it(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), security=MailSecurity.TLS)
        with pytest.raises(MailServerError) as caught:
            await server.folders(login)
        assert caught.value.reason.code is ReasonCode.MAIL_TLS_FAILED
