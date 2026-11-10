"""Streaming multipart upload: each file part goes to a temporary file in chunks and is hashed
on the way, so an upload is never held in memory. The size limit is enforced while receiving:
early by `Content-Length`, otherwise as soon as the file parts, or the whole body, grow beyond
it (the body may exceed the file limit by `_OVERHEAD` for framing and small fields, and by the
limits of larger ones).

Expected form: file parts of one name with a filename (`read_upload`: one part `file`;
`read_uploads`: up to a number of parts of a name of the caller's), and optional text fields;
only the fields the caller names are kept, others are skipped.
"""

import asyncio
import hashlib
import os
import re
import tempfile
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, BinaryIO, cast

from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import Request

from lekto.core.domain.documents import Sha256
from lekto.core.services.pipeline import IncomingFile

if TYPE_CHECKING:
    from python_multipart.multipart import MultipartCallbacks

FILE_FIELD = "file"
_FIELD_LIMIT = 1024  # bytes of a text field
_OVERHEAD = 64 * 1024  # bytes of multipart framing and small text fields beyond the files
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FILENAME = 255


class UploadTooLargeError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"the file is larger than {limit} bytes")
        self.limit = limit


class MalformedUploadError(Exception):
    """The request is not the expected multipart form."""


@dataclass
class Upload:
    file: IncomingFile
    filename: str
    fields: dict[str, str]


@dataclass(frozen=True)
class ReceivedFile:
    file: IncomingFile
    filename: str


@dataclass
class Uploads:
    files: list[ReceivedFile]
    fields: dict[str, str]

    async def remove(self) -> None:
        """Remove the temporary files."""
        for item in self.files:
            await asyncio.shield(asyncio.to_thread(item.file.path.unlink, missing_ok=True))


async def read_upload(
    request: Request,
    *,
    max_size: int,
    fields: Collection[str] = (),
    limits: Mapping[str, int] | None = None,
) -> Upload:
    """Read the multipart body of `request` with one file part `file`, keeping the text fields
    named in `fields` (each up to 1 KiB, or its limit in `limits`). The caller removes
    `upload.file.path` when done; on error nothing is left behind."""
    uploads = await read_uploads(
        request,
        max_size=max_size,
        file_field=FILE_FIELD,
        max_files=1,
        fields=fields,
        limits=limits,
    )
    if not uploads.files:
        raise MalformedUploadError(f"the form has no file part '{FILE_FIELD}'")
    (received,) = uploads.files
    return Upload(file=received.file, filename=received.filename, fields=uploads.fields)


async def read_uploads(
    request: Request,
    *,
    max_size: int,
    file_field: str,
    max_files: int,
    fields: Collection[str] = (),
    limits: Mapping[str, int] | None = None,
) -> Uploads:
    """Read the multipart body of `request`: up to `max_files` file parts named `file_field`,
    `max_size` bytes together, and the text fields named in `fields` (each up to 1 KiB, or its
    limit in `limits`). The caller removes the files when done (`Uploads.remove`); on error
    nothing is left behind."""
    content_type, options = parse_options_header(request.headers.get("content-type"))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise MalformedUploadError("expected multipart/form-data with a boundary")
    limits = dict(limits or {})
    body_limit = max_size + _OVERHEAD + sum(limits.values())
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > body_limit:
        raise UploadTooLargeError(max_size)
    state = _State(file_field, max_files, max_size, frozenset(fields), limits)
    try:
        parser = MultipartParser(boundary, cast("MultipartCallbacks", state.callbacks()))
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > body_limit:
                raise UploadTooLargeError(max_size)
            try:
                parser.write(chunk)
            except MultipartParseError as error:
                raise MalformedUploadError(f"invalid multipart body: {error}") from None
            state.check()
            await state.flush()
        if not state.finished:
            raise MalformedUploadError("the multipart body is incomplete")
        await state.flush()
        await state.close()
        return Uploads(
            files=[
                ReceivedFile(
                    file=IncomingFile(
                        path=cast(Path, item.path),
                        sha256=Sha256(item.digest.hexdigest()),
                        size=item.size,
                    ),
                    filename=item.filename,
                )
                for item in state.files
            ],
            fields=state.fields,
        )
    except BaseException:
        await asyncio.shield(state.discard())
        raise


@dataclass
class _File:
    """A file part: its name, and the temporary file it goes to once data comes."""

    filename: str
    digest: Any = field(default_factory=hashlib.sha256)
    size: int = 0
    path: Path | None = None
    target: BinaryIO | None = None


@dataclass
class _State:
    """Collects the parser's callbacks; the file data is written between parser calls."""

    file_field: str
    max_files: int
    max_size: int
    wanted: frozenset[str]
    limits: dict[str, int]
    size: int = 0  # of all files
    files: list[_File] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    finished: bool = False
    _pending: list[tuple[_File, bytes]] = field(default_factory=list)
    _headers: dict[str, str] = field(default_factory=dict)
    _header_field: bytearray = field(default_factory=bytearray)
    _header_value: bytearray = field(default_factory=bytearray)
    _part: str | _File | None = None  # a file, the name of a text field, or None (ignored)
    _value: bytearray = field(default_factory=bytearray)
    _error: Exception | None = None

    def callbacks(self) -> dict[str, Callable[..., None]]:
        return {
            "on_part_begin": self._part_begin,
            "on_header_field": self._header_field_data,
            "on_header_value": self._header_value_data,
            "on_header_end": self._header_end,
            "on_headers_finished": self._headers_finished,
            "on_part_data": self._part_data,
            "on_part_end": self._part_end,
            "on_end": self._end,
        }

    def check(self) -> None:
        if self._error is not None:
            raise self._error

    async def flush(self) -> None:
        """Write what came, each file's to its temporary file (made for every file part, also
        one without data)."""
        for item in self.files:
            if item.target is None:
                descriptor, name = await asyncio.to_thread(tempfile.mkstemp, prefix="lekto-upload-")
                item.path = Path(name)
                item.target = os.fdopen(descriptor, "wb")
        pending, self._pending = self._pending, []
        for item, data in pending:
            assert item.target is not None
            await asyncio.to_thread(item.target.write, data)

    async def close(self) -> None:
        for item in self.files:
            if item.target is not None and not item.target.closed:
                await asyncio.to_thread(item.target.close)

    async def discard(self) -> None:
        await self.close()
        for item in self.files:
            if item.path is not None:
                await asyncio.to_thread(item.path.unlink, missing_ok=True)

    def _part_begin(self) -> None:
        self._headers = {}
        self._part = None
        self._value = bytearray()

    def _header_field_data(self, data: bytes, start: int, end: int) -> None:
        self._header_field += data[start:end]

    def _header_value_data(self, data: bytes, start: int, end: int) -> None:
        self._header_value += data[start:end]

    def _header_end(self) -> None:
        name = self._header_field.decode("latin-1").lower()
        # As latin-1 the bytes survive `parse_options_header`, which encodes them as latin-1 again;
        # names and file names are decoded as UTF-8 afterwards (a file name may hold any letter).
        self._headers[name] = self._header_value.decode("latin-1")
        self._header_field, self._header_value = bytearray(), bytearray()

    def _headers_finished(self) -> None:
        disposition, options = parse_options_header(self._headers.get("content-disposition"))
        if disposition != b"form-data" or b"name" not in options:
            self._fail(MalformedUploadError("a part has no form-data name"))
            return
        name = options[b"name"].decode("utf-8", errors="replace")
        if name == self.file_field:
            if len(self.files) >= self.max_files:
                self._fail(
                    MalformedUploadError(
                        "only one file per upload"
                        if self.max_files == 1
                        else f"at most {self.max_files} files"
                    )
                )
                return
            raw = options.get(b"filename", b"").decode("utf-8", errors="replace")
            self.files.append(_File(clean_filename(raw)))
            self._part = self.files[-1]
        elif b"filename" in options or name not in self.wanted:
            self._part = None  # other files and unknown fields are skipped
        else:
            self._part = name

    def _part_data(self, data: bytes, start: int, end: int) -> None:
        if self._part is None or self._error is not None:
            return
        chunk = data[start:end]
        if isinstance(self._part, _File):
            self.size += len(chunk)
            if self.size > self.max_size:
                self._fail(UploadTooLargeError(self.max_size))
                return
            self._part.size += len(chunk)
            self._part.digest.update(chunk)
            self._pending.append((self._part, chunk))
        else:
            self._value += chunk
            if len(self._value) > self.limits.get(self._part, _FIELD_LIMIT):
                self._fail(MalformedUploadError(f"the field '{self._part}' is too long"))

    def _part_end(self) -> None:
        if isinstance(self._part, str):
            self.fields[self._part] = self._value.decode("utf-8", errors="replace")

    def _end(self) -> None:
        self.finished = True

    def _fail(self, error: Exception) -> None:
        if self._error is None:
            self._error = error


def upload_body(file: str, **fields: object) -> dict[str, Any]:
    """The OpenAPI request body (`openapi_extra`) of an upload read with `read_upload`: the file
    part, described by `file`, and the optional text `fields` with their schemas."""
    return {
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": [FILE_FIELD],
                        "properties": {
                            FILE_FIELD: {"type": "string", "format": "binary", "description": file},
                            **fields,
                        },
                    }
                }
            },
        }
    }


def clean_filename(raw: str) -> str:
    """The last path segment, without control characters; `upload` if nothing is left."""
    name = PurePosixPath(raw.replace("\\", "/")).name
    name = _CONTROL.sub("", name).strip()
    name = name[:_MAX_FILENAME]
    return name if name not in ("", ".", "..") else "upload"
