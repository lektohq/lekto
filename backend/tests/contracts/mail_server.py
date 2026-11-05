"""Contract suite for `MailServer`. The adapter test provides a `world`: a server where it can
make a new account for a test, and an address where nobody listens."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Protocol

import pytest

from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.reasons import ReasonCode
from lekto.core.ports.mail_server import MailSearch, MailServer, MailServerError
from tests.mails import plain_mail

EARLY = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
LATE = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)


def _lines(data: bytes | None) -> bytes | None:
    return None if data is None else data.replace(b"\r\n", b"\n")


class MailWorld(Protocol):
    def account(self, folders: Sequence[str] = (), *, password: str = "secret") -> MailLogin:
        """A new account with `INBOX` and `folders`, on a server without TLS."""
        ...

    def unreachable(self) -> MailLogin:
        """A login for an address where nobody listens."""
        ...

    def deliver(
        self,
        login: MailLogin,
        folder: str,
        data: bytes,
        *,
        arrived_at: datetime,
        seen: bool = False,
        flags: Sequence[str] = (),
    ) -> None:
        """Put a mail into the account's `folder`, with IMAP `flags` and keywords."""
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
        assert (await server.account(login)).folders == (
            "INBOX",
            "Belege & Co",
            "Bestätigungen",
            "Rechnungen",
        )

    async def test_a_new_account_has_its_inbox(self, server: MailServer, world: MailWorld) -> None:
        assert (await server.account(world.account())).folders == ("INBOX",)

    async def test_a_password_beyond_ascii(self, server: MailServer, world: MailWorld) -> None:
        login = world.account(password="Grüße-1")
        assert (await server.account(login)).folders == ("INBOX",)

    async def test_a_wrong_password_is_refused(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), password="wrong")
        with pytest.raises(MailServerError) as caught:
            await server.account(login)
        assert caught.value.reason.code is ReasonCode.MAIL_LOGIN_FAILED

    async def test_an_unknown_user_is_refused(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), username="nobody-here")
        with pytest.raises(MailServerError) as caught:
            await server.account(login)
        assert caught.value.reason.code is ReasonCode.MAIL_LOGIN_FAILED

    async def test_an_address_where_nobody_listens(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.unreachable()
        with pytest.raises(MailServerError) as caught:
            await server.account(login)
        assert caught.value.reason.code is ReasonCode.MAIL_UNREACHABLE
        assert caught.value.reason.params == {"host": login.host}

    async def test_tls_with_a_server_without_it(self, server: MailServer, world: MailWorld) -> None:
        login = replace(world.account(), security=MailSecurity.TLS)
        with pytest.raises(MailServerError) as caught:
            await server.account(login)
        assert caught.value.reason.code is ReasonCode.MAIL_TLS_FAILED

    async def test_a_session_finds_reads_and_leaves_mails_unread(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.account(["Rechnungen"])
        first, second = plain_mail("Erste"), plain_mail("Zweite")
        world.deliver(login, "INBOX", first, arrived_at=EARLY)
        world.deliver(login, "INBOX", second, arrived_at=LATE)
        world.deliver(login, "INBOX", plain_mail("Gelesen"), arrived_at=LATE, seen=True)
        async with server.session(login) as session:
            found = await session.search("INBOX", MailSearch())
            assert len(found.uids) == 3 and list(found.uids) == sorted(found.uids)
            assert found.uidvalidity > 0
            one, two, _ = found.uids
            infos = await session.info("INBOX", [two, one])
            assert [info.uid for info in infos] == [two, one]
            assert infos[1].arrived_at == EARLY and infos[1].size >= len(first)
            assert _lines(await session.fetch("INBOX", one)) == _lines(first)
            head = _lines(await session.head("INBOX", one)) or b""
            assert b"Subject: Erste" in head and b"Hallo Anna" not in head
            unseen = await session.search("INBOX", MailSearch(unseen=True))
            assert unseen.uids == (one, two)  # fetching marked nothing
            since = await session.search("INBOX", MailSearch(since=date(2026, 11, 3)))
            assert since.uids == (two, found.uids[2])
            await session.mark("INBOX", one, add=["\\Seen"])
            assert (await session.search("INBOX", MailSearch(unseen=True))).uids == (two,)
            assert (await session.search("Rechnungen", MailSearch())).uids == ()

    async def test_a_session_reads_flags_and_keywords(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.account()
        world.deliver(
            login,
            "INBOX",
            plain_mail("Markiert"),
            arrived_at=EARLY,
            flags=["\\Flagged", "$MailFlagBit1", "Lekto", "$Forwarded"],
        )
        world.deliver(login, "INBOX", plain_mail("Schlicht"), arrived_at=LATE, seen=True)
        async with server.session(login) as session:
            found = await session.search("INBOX", MailSearch())
            one, two = found.uids
            flagged, plain = await session.info("INBOX", [one, two])
            assert {"\\Flagged", "$MailFlagBit1", "Lekto"} <= flagged.flags
            assert "\\Seen" in plain.flags and "Lekto" not in plain.flags
            assert "Lekto" in found.keywords  # $Forwarded is a client's own: not offered
            assert "$Forwarded" not in found.keywords and "$MailFlagBit1" not in found.keywords
            assert found.own_keywords
            await session.mark("INBOX", two, add=["\\Flagged", "Erledigt"], remove=["\\Seen"])
            await session.mark("INBOX", one, remove=["lekto", "$MailFlagBit1"])
            again = {info.uid: info.flags for info in await session.info("INBOX", [one, two])}
            assert {"\\Flagged", "Erledigt"} <= again[two] and "\\Seen" not in again[two]
            assert "Lekto" not in again[one] and "$MailFlagBit1" not in again[one]
            assert "\\Flagged" in again[one]
        account = await server.account(login)
        assert "Lekto" in account.keywords and account.own_keywords

    async def test_a_session_moves_and_throws_away(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = world.account(["Archiv"])
        world.deliver(login, "INBOX", plain_mail("Eins"), arrived_at=EARLY)
        world.deliver(login, "INBOX", plain_mail("Zwei"), arrived_at=EARLY)
        async with server.session(login) as session:
            one, two = (await session.search("INBOX", MailSearch())).uids
            await session.move("INBOX", one, "Archiv")
            assert len((await session.search("Archiv", MailSearch())).uids) == 1
            with pytest.raises(MailServerError) as caught:
                await session.move("INBOX", two, "Nirgends")
            assert caught.value.reason.code is ReasonCode.MAIL_FOLDER_MISSING
            await session.trash("INBOX", two)
            assert (await session.search("INBOX", MailSearch())).uids == ()
            assert await session.fetch("INBOX", two) is None

    async def test_a_missing_folder(self, server: MailServer, world: MailWorld) -> None:
        login = world.account()
        async with server.session(login) as session:
            with pytest.raises(MailServerError) as caught:
                await session.search("Nirgends", MailSearch())
        assert caught.value.reason.code is ReasonCode.MAIL_FOLDER_MISSING
        assert caught.value.reason.params == {"folder": "Nirgends"}

    async def test_a_session_with_a_wrong_password(
        self, server: MailServer, world: MailWorld
    ) -> None:
        login = replace(world.account(), password="wrong")
        with pytest.raises(MailServerError) as caught:
            async with server.session(login):
                pass
        assert caught.value.reason.code is ReasonCode.MAIL_LOGIN_FAILED
