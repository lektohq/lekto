"""Mail servers over IMAP (`imaplib` of the standard library, in a thread)."""

from lekto.adapters.outbound.imap.server import ImapMailServer

__all__ = ["ImapMailServer"]
