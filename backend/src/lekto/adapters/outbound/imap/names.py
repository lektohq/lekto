"""Folder names in IMAP's modified UTF-7 (RFC 3501, 5.1.3) and the lines of a LIST answer."""

import base64
import re

_LIST = re.compile(rb'\((?P<flags>[^)]*)\) (?P<delimiter>NIL|"(?:[^"\\]|\\.)*") (?P<name>.*)')


def decode(name: bytes) -> str:
    """A folder name as the server sends it, as text: `&...-` is UTF-16 in a modified base64,
    `&-` is `&`."""
    text = name.decode("ascii")
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("&", index)
        if start < 0:
            out.append(text[index:])
            break
        out.append(text[index:start])
        end = text.find("-", start)
        if end < 0:
            raise ValueError(f"unterminated shift in folder name {text!r}")
        chunk = text[start + 1 : end]
        if not chunk:
            out.append("&")
        else:
            data = chunk.replace(",", "/")
            data += "=" * (-len(data) % 4)
            out.append(base64.b64decode(data).decode("utf-16-be"))
        index = end + 1
    return "".join(out)


def encode(name: str) -> bytes:
    """A folder name as the server expects it (the reverse of `decode`)."""
    out: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            data = base64.b64encode("".join(pending).encode("utf-16-be")).decode("ascii")
            out.append("&" + data.rstrip("=").replace("/", ",") + "-")
            pending.clear()

    for character in name:
        if 0x20 <= ord(character) <= 0x7E:
            flush()
            out.append("&-" if character == "&" else character)
        else:
            pending.append(character)
    flush()
    return "".join(out).encode("ascii")


def quoted(name: str) -> bytes:
    """`encode(name)` as an IMAP quoted string."""
    return b'"' + encode(name).replace(b"\\", b"\\\\").replace(b'"', b'\\"') + b'"'


def listed(entries: list[bytes | tuple[bytes, bytes] | None]) -> list[tuple[str, frozenset[str]]]:
    """The folders of a LIST answer (as `imaplib` gives it: a line, or a line and a literal for
    a name the server sends as one) with their flags, lower case (`\\noselect`, ...)."""
    found: list[tuple[str, frozenset[str]]] = []
    for entry in entries:
        if entry is None:
            continue
        line, literal = entry if isinstance(entry, tuple) else (entry, None)
        match = _LIST.match(line)
        if match is None:
            continue
        flags = frozenset(flag.lower() for flag in match["flags"].decode("ascii").split())
        if literal is not None:
            raw = literal
        else:
            raw = match["name"].strip()
            if raw.startswith(b'"') and raw.endswith(b'"'):
                raw = re.sub(rb"\\(.)", rb"\1", raw[1:-1])
        found.append((decode(raw), flags))
    return found
