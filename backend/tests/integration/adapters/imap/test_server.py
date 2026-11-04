"""The IMAP adapter passes the contract suite against GreenMail: each test gets its own account
through GreenMail's API, so tests in parallel do not see each other's folders."""

import imaplib
import json
import secrets
import urllib.request
from collections.abc import Sequence

import pytest

from lekto.adapters.outbound.imap import ImapMailServer
from lekto.adapters.outbound.imap.names import quoted
from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.ports.mail_server import MailServer
from tests import probes
from tests.contracts.mail_server import MailServerContract, MailWorld

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class _GreenMail:
    def __init__(self, host: str, port: int, api: str) -> None:
        self._host, self._port, self._api = host, port, api

    def account(self, folders: Sequence[str] = (), *, password: str = "secret") -> MailLogin:
        username = f"t{secrets.token_hex(6)}"
        body = {"email": f"{username}@lekto.test", "login": username, "password": password}
        request = urllib.request.Request(
            f"{self._api}/api/user",
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with _opener.open(request, timeout=probes.TIMEOUT) as response:
            assert response.status == 200
        login = MailLogin(
            host=self._host,
            port=self._port,
            security=MailSecurity.NONE,
            username=username,
            password=password,
        )
        if folders:
            with imaplib.IMAP4(self._host, self._port, timeout=probes.TIMEOUT) as imap:
                imap.login(username, password)
                for folder in folders:
                    status, answer = imap._simple_command("CREATE", quoted(folder).decode())
                    assert status == "OK", answer
        return login

    def unreachable(self) -> MailLogin:
        return MailLogin(
            host="127.0.0.1",
            port=probes.free_port(),
            security=MailSecurity.NONE,
            username="u",
            password="p",
        )


class TestImapMailServer(MailServerContract):
    @pytest.fixture
    def server(self) -> MailServer:
        return ImapMailServer()

    @pytest.fixture
    def world(self, greenmail: tuple[str, int, str]) -> MailWorld:
        return _GreenMail(*greenmail)
