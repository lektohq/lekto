"""The in-memory mail server passes the contract suite."""

import secrets
from collections.abc import Sequence
from datetime import datetime

import pytest

from lekto.adapters.outbound.memory import MemoryMailServer
from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.ports.mail_server import MailServer
from tests.contracts.mail_server import MailServerContract, MailWorld


class _World:
    def __init__(self, server: MemoryMailServer) -> None:
        self._server = server

    def account(self, folders: Sequence[str] = (), *, password: str = "secret") -> MailLogin:
        login = MailLogin(
            host="mail.test",
            port=143,
            security=MailSecurity.NONE,
            username=f"user-{secrets.token_hex(4)}",
            password=password,
        )
        self._server.add_account(login).add_folders(*folders)
        return login

    def deliver(
        self,
        login: MailLogin,
        folder: str,
        data: bytes,
        *,
        arrived_at: datetime,
        seen: bool = False,
    ) -> None:
        account = self._server.servers[(login.host, login.port)][login.username]
        account.deliver(folder, data, arrived_at=arrived_at, seen=seen)

    def unreachable(self) -> MailLogin:
        return MailLogin(
            host="nobody.test", port=143, security=MailSecurity.NONE, username="u", password="p"
        )


class TestMemoryMailServer(MailServerContract):
    @pytest.fixture
    def server(self) -> MailServer:
        return MemoryMailServer()

    @pytest.fixture
    def world(self, server: MailServer) -> MailWorld:
        assert isinstance(server, MemoryMailServer)
        return _World(server)
