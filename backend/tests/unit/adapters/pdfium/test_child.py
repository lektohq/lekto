"""PDFium reads the pages of a PDF in a child: a PDF that needs too much memory or time fails its
step, not the worker; a page PDFium cannot load is a file it cannot read (AD-06)."""

import io
import json
import resource
import signal
from collections.abc import Awaitable, Callable, Sequence
from datetime import timedelta
from pathlib import Path

import pytest

from lekto.adapters.outbound.pdfium import (
    LayoutParser,
    PdfiumPageRenderer,
    PdfiumTextLocator,
    TextLayer,
    text_layer,
)
from lekto.adapters.outbound.pdfium import child as module
from lekto.adapters.outbound.pdfium.child import (
    OUT_OF_MEMORY,
    UNPROCESSABLE,
    Task,
    run_child,
    serve,
)
from lekto.adapters.outbound.pdfium.library import MODULE
from lekto.adapters.outbound.system import Completed
from lekto.adapters.outbound.zxing import ZxingCodeReader
from lekto.core.domain import media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.reasons import ReasonCode, because
from tests.pdfs import missing_page, text_bomb

MEMORY = 768 * 1024**2  # an ordinary PDF needs far less

type Reading = Callable[[Path, Path], Awaitable[object]]


def _readings(memory: int | None) -> dict[str, Reading]:
    """Each way the adapters read a PDF, given the PDF and a folder of its own."""

    async def pages(pdf: Path, work: Path) -> object:
        renderer = PdfiumPageRenderer(memory=memory)
        return await renderer.render_pages(pdf, media_type=media_types.PDF, target=work)

    async def parse(pdf: Path, work: Path) -> object:
        parser = LayoutParser(memory=memory)
        return await parser.parse(pdf, text=work / "text.txt", structure=work / "structure.json")

    async def locate(pdf: Path, work: Path) -> object:
        return await PdfiumTextLocator(memory=memory).locate(pdf, ["Muster"])

    async def codes(pdf: Path, work: Path) -> object:
        return await ZxingCodeReader(memory=memory).read_codes(pdf, every_page=True)

    async def layer(pdf: Path, work: Path) -> object:
        return await text_layer(pdf, memory=memory)

    return {"text-layer": layer, "pages": pages, "parse": parse, "locate": locate, "codes": codes}


@pytest.mark.parametrize("reading", list(_readings(None)))
async def test_a_pdf_that_needs_too_much_memory_fails_its_step_not_the_worker(
    tmp_path: Path, reading: str
) -> None:
    bomb = text_bomb(tmp_path / "bomb.pdf", 6_000_000)  # 62 KB, 3.4 GB in the worker before
    work = tmp_path / "work"
    work.mkdir()
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with pytest.raises(UnprocessableDocumentError) as raised:
        await _readings(MEMORY)[reading](bomb, work)
    assert raised.value.reason.code is ReasonCode.PDF_TOO_COMPLEX
    grown = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before  # KiB on Linux
    assert grown < 200 * 1024
    assert list(work.iterdir()) == []  # nothing half written stays


async def test_a_child_out_of_time_fails_its_step(tmp_path: Path) -> None:
    pdf = text_bomb(tmp_path / "small.pdf", 10)
    with pytest.raises(UnprocessableDocumentError) as raised:
        await run_child(
            MODULE, "text-layer", [str(pdf)], timeout=timedelta(milliseconds=1), memory=None
        )
    assert raised.value.reason.code is ReasonCode.PDF_TOO_COMPLEX


async def test_a_page_pdfium_cannot_load_is_a_pdf_it_cannot_read(tmp_path: Path) -> None:
    pdf = missing_page(tmp_path / "missing.pdf")
    readings = _readings(None)
    # The checks before the OCR leave it to OCRmyPDF to say why; the locator skips the page.
    assert await readings["text-layer"](pdf, tmp_path) == TextLayer(unreadable=False, hidden=False)
    assert await readings["locate"](pdf, tmp_path) == [()]
    for reading in ("pages", "parse", "codes"):
        work = tmp_path / reading
        work.mkdir()
        with pytest.raises(UnprocessableDocumentError) as raised:
            await readings[reading](pdf, work)
        assert raised.value.reason.code is ReasonCode.PDF_UNREADABLE_DETAIL, reading
        assert str(raised.value) == "the PDF cannot be read: page 2: Failed to load page."
        assert list(work.iterdir()) == []


REASON = json.dumps(because(ReasonCode.PDF_ENCRYPTED).to_json())


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [
        (UNPROCESSABLE, REASON, ReasonCode.PDF_ENCRYPTED),
        (OUT_OF_MEMORY, "", ReasonCode.PDF_TOO_COMPLEX),
        (-signal.SIGABRT, "", ReasonCode.PDF_TOO_COMPLEX),  # PDFium out of memory
        (-signal.SIGKILL, "", ReasonCode.PDF_TOO_COMPLEX),  # the kernel's OOM killer
        (-signal.SIGSEGV, "", ReasonCode.PDF_UNREADABLE_DETAIL),  # PDFium crashed on it
    ],
)
async def test_how_a_child_ends_says_what_the_file_is(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str, expected: ReasonCode
) -> None:
    async def ended(args: Sequence[str], **_: object) -> Completed:
        return Completed(returncode=returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(module, "run_process", ended)
    with pytest.raises(UnprocessableDocumentError) as raised:
        await run_child(MODULE, "pages", [], timeout=timedelta(minutes=1), memory=None)
    assert raised.value.reason.code is expected


@pytest.mark.parametrize(
    ("returncode", "stdout"), [(1, ""), (0, "not json"), (UNPROCESSABLE, "not json")]
)
async def test_any_other_end_is_an_error_of_lektos(
    monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    async def ended(args: Sequence[str], **_: object) -> Completed:
        return Completed(returncode=returncode, stdout=stdout, stderr="Traceback\nKeyError: 'x'")

    monkeypatch.setattr(module, "run_process", ended)
    with pytest.raises(RuntimeError):
        await run_child(MODULE, "pages", [], timeout=timedelta(minutes=1), memory=None)


def _served(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], task: Task, given: str
) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(given))
    code = serve(MODULE, {"task": task}, ["task", "argument"])
    return code, capsys.readouterr().out


def test_the_child_prints_its_answer_or_why_it_cannot(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def answers(args: Sequence[str], given: JsonValue) -> JsonValue:
        return {"args": list(args), "given": given}

    assert _served(monkeypatch, capsys, answers, '["a"]') == (
        0,
        '{"args": ["argument"], "given": ["a"]}',
    )
    assert json.loads(_served(monkeypatch, capsys, answers, "")[1])["given"] is None

    def unprocessable(args: Sequence[str], given: JsonValue) -> JsonValue:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_ENCRYPTED))

    assert _served(monkeypatch, capsys, unprocessable, "") == (UNPROCESSABLE, REASON)

    def too_large(args: Sequence[str], given: JsonValue) -> JsonValue:
        raise MemoryError

    assert _served(monkeypatch, capsys, too_large, "") == (OUT_OF_MEMORY, "")
    assert serve(MODULE, {"task": answers}, ["other"]) == 2
