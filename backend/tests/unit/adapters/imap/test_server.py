"""Signing in, against a stand-in for `imaplib`: the capabilities the session goes by are the
server's after the login, not those of its greeting."""

import imaplib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from types import MethodType

import pytest

from lekto.adapters.outbound.imap.server import (
    NO_IMAP,
    ImapMailServer,
    _folders,
    _guarded,
    _leave,
)
from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.mail_server import MailServerError
from tests.builders import DEFAULT_SETTINGS


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


class Listing:
    def __init__(self, *names: bytes) -> None:
        self._names = names

    def list(self) -> tuple[str, list[bytes]]:
        return "OK", [b'(\\HasNoChildren) "/" "' + name + b'"' for name in self._names]


def test_the_folders_of_an_account_keep_names_sent_against_the_standard() -> None:
    """One name the server sends in UTF-8 or with a bare `&` broke the whole list."""
    listing = Listing(b"INBOX", b"R&D", "Entwürfe".encode(), b"Best&AOQ-tigungen")
    assert _folders(listing) == ("INBOX", "Bestätigungen", "Entwürfe", "R&D")  # type: ignore[arg-type]


LOGIN = MailLogin(
    host="mail.example.org",
    port=993,
    security=MailSecurity.TLS,
    username="someone",
    password="secret",
)


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out"), OSError("reset"), imaplib.IMAP4.abort("socket error: EOF")],
)
def test_a_silent_or_lost_server_cannot_be_reached(error: Exception) -> None:
    """Also in `account`: no raw TimeoutError, no "answered with an error" (AD-14)."""

    def work(*_: object) -> None:
        raise error

    with pytest.raises(MailServerError) as caught:
        _guarded(LOGIN.host, work)
    assert caught.value.reason == because(ReasonCode.MAIL_UNREACHABLE, host=LOGIN.host)

    @contextmanager
    def session(self: ImapMailServer, login: MailLogin) -> Iterator[object]:
        yield object()

    server = ImapMailServer(timeout=DEFAULT_SETTINGS.mail_timeout)
    server._session = MethodType(session, server)  # type: ignore[method-assign]
    with pytest.raises(MailServerError) as caught:
        server._run(LOGIN, work)
    assert caught.value.reason == because(ReasonCode.MAIL_UNREACHABLE, host=LOGIN.host)


def test_a_refusal_names_the_server_s_words() -> None:
    def refused() -> None:
        raise imaplib.IMAP4.error([b"[CANNOT] Invalid flags"])

    with pytest.raises(MailServerError) as caught:
        _guarded(LOGIN.host, refused)
    assert caught.value.reason == because(
        ReasonCode.MAIL_SERVER_ERROR, detail="[CANNOT] Invalid flags"
    )


class Leaving:
    def __init__(self) -> None:
        self.closed = False

    def logout(self) -> None:
        raise imaplib.IMAP4.abort("socket error: EOF")

    def shutdown(self) -> None:
        self.closed = True


def test_a_failed_logout_still_closes_the_connection() -> None:
    """`imaplib` shuts the socket only after a LOGOUT that worked (AD-K11)."""
    imap = Leaving()
    _leave(imap)  # type: ignore[arg-type]
    assert imap.closed


def test_a_service_that_is_no_imap_server_is_not_quoted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test of a mailbox may name any host and port: what answers there is not shown, it may
    be any service in the network (XB-K01)."""

    class NotImap(imaplib.IMAP4_SSL):
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise imaplib.IMAP4.abort("unexpected response: b'HTTP/1.1 400 Bad Request'")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", NotImap)
    server = ImapMailServer(timeout=DEFAULT_SETTINGS.mail_timeout)
    with pytest.raises(MailServerError) as caught:
        server._connect(LOGIN)
    assert caught.value.reason == because(ReasonCode.MAIL_SERVER_ERROR, detail=NO_IMAP)
    assert "HTTP" not in str(caught.value)
