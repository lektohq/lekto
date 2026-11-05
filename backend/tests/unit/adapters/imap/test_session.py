"""What the IMAP session sends for a move and for the trash, against a stand-in for `imaplib`:
MOVE where the server has it, else COPY and a deletion; one mail expunged alone with UIDPLUS, or
left marked without it, never the folder's other marked mails."""

from collections.abc import Sequence

import pytest

from lekto.adapters.outbound.imap.session import ImapMailSession

Sent = tuple[str, ...]


class FakeImap:
    def __init__(
        self,
        capabilities: Sequence[str] = ("IMAP4rev1", "MOVE", "UIDPLUS"),
        folders: Sequence[tuple[str, Sequence[str]]] = (("INBOX", ()), ("Trash", ("\\Trash",))),
    ) -> None:
        self.capabilities = tuple(capabilities)
        self.sent: list[Sent] = []
        self._folders = folders

    def select(self, name: str) -> tuple[str, list[bytes]]:
        self.sent.append(("SELECT", name))
        return "OK", [b"1"]

    def response(self, key: str) -> tuple[str, list[bytes | None]]:
        return key, [b"42"] if key == "UIDVALIDITY" else [None]

    def uid(self, command: str, *args: str) -> tuple[str, list[None]]:
        self.sent.append(("UID", command, *args))
        return "OK", [None]

    def expunge(self) -> tuple[str, list[None]]:
        self.sent.append(("EXPUNGE",))
        return "OK", [None]

    def list(self) -> tuple[str, list[bytes]]:
        lines = [
            b'(%s) "/" "%s"' % (" ".join(flags).encode(), name.encode())
            for name, flags in self._folders
        ]
        return "OK", lines


def _session(imap: FakeImap) -> ImapMailSession:
    return ImapMailSession(imap, lambda work, *args: work(*args))  # type: ignore[arg-type]


def _commands(imap: FakeImap) -> list[Sent]:
    return [sent for sent in imap.sent if sent[0] != "SELECT"]


async def test_a_move_with_the_move_command() -> None:
    imap = FakeImap()
    await _session(imap).move("INBOX", 7, "Archiv")
    assert _commands(imap) == [("UID", "MOVE", "7", '"Archiv"')]


async def test_a_move_without_it_copies_and_expunges_the_one_mail() -> None:
    imap = FakeImap(capabilities=("IMAP4rev1", "UIDPLUS"))
    await _session(imap).move("INBOX", 7, "Archiv")
    assert _commands(imap) == [
        ("UID", "COPY", "7", '"Archiv"'),
        ("UID", "STORE", "7", "+FLAGS", "(\\Deleted)"),
        ("UID", "EXPUNGE", "7"),
    ]


async def test_without_uidplus_the_mail_stays_marked() -> None:
    imap = FakeImap(capabilities=("IMAP4rev1",))
    await _session(imap).move("INBOX", 7, "Archiv")
    assert _commands(imap) == [
        ("UID", "COPY", "7", '"Archiv"'),
        ("UID", "STORE", "7", "+FLAGS", "(\\Deleted)"),
    ]
    assert ("EXPUNGE",) not in imap.sent  # that would take every mail anyone marked


async def test_the_trash_is_the_folder_flagged_as_such() -> None:
    imap = FakeImap()
    await _session(imap).trash("INBOX", 7)
    assert _commands(imap) == [("UID", "MOVE", "7", '"Trash"')]


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        (
            ("IMAP4rev1", "UIDPLUS"),
            [("UID", "STORE", "7", "+FLAGS", "(\\Deleted)"), ("UID", "EXPUNGE", "7")],
        ),
        (("IMAP4rev1",), [("UID", "STORE", "7", "+FLAGS", "(\\Deleted)")]),
    ],
)
async def test_without_a_trash_folder_the_mail_is_deleted_alone(
    capabilities: Sequence[str], expected: list[Sent]
) -> None:
    imap = FakeImap(capabilities=capabilities, folders=[("INBOX", ()), ("Archiv", ())])
    await _session(imap).trash("INBOX", 7)
    assert _commands(imap) == expected
    assert ("EXPUNGE",) not in imap.sent
