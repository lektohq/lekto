"""Signing in, against a stand-in for `imaplib`: the capabilities the session goes by are the
server's after the login, not those of its greeting."""

from collections.abc import Sequence

import pytest

from lekto.adapters.outbound.imap.server import ImapMailServer
from lekto.core.domain.mail import MailLogin, MailSecurity


class SigningIn:
    def __init__(self, answer: tuple[str, Sequence[bytes | None]] | Exception) -> None:
        self.capabilities: tuple[str, ...] = ("IMAP4REV1", "AUTH=PLAIN")
        self.state = "NONAUTH"
        self._answer = answer

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        self.state = "AUTH"
        return "OK", [b"signed in"]

    def capability(self) -> tuple[str, Sequence[bytes | None]]:
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _sign_in(imap: SigningIn) -> None:
    login = MailLogin(
        host="mail.example.org",
        port=993,
        security=MailSecurity.TLS,
        username="someone",
        password="secret",
    )
    ImapMailServer._sign_in(imap, login)  # type: ignore[arg-type]


def test_the_capabilities_after_the_login_count() -> None:
    imap = SigningIn(("OK", [b"IMAP4rev1 UIDPLUS move IDLE"]))
    _sign_in(imap)
    assert imap.capabilities == ("IMAP4REV1", "UIDPLUS", "MOVE", "IDLE")


@pytest.mark.parametrize(
    "answer",
    [("NO", [b"not now"]), ("OK", []), ("OK", [None]), OSError("gone")],
    ids=["refused", "empty", "nothing", "broken"],
)
def test_without_an_answer_the_greetings_capabilities_stay(
    answer: tuple[str, Sequence[bytes | None]] | Exception,
) -> None:
    imap = SigningIn(answer)
    _sign_in(imap)
    assert imap.capabilities == ("IMAP4REV1", "AUTH=PLAIN")
