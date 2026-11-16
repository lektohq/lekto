"""PDFium in a process of its own, with the time and memory limits of `run_process`.

PDFium builds an object for every text operator of a page, and a content stream of millions of
them packs into a few kilobytes: a PDF of 62 KB took 3.4 GB and 27 s in the worker, which the
kernel then ended with every job it held, again on each attempt of the node. In a child such a
PDF fails its step, not the worker, and holds no lock of the worker's. Out of memory, PDFium
aborts at once; a child started for nothing but reading a PDF costs about 0.15 s.

The parent runs `python -m <module> TASK ARGS...` (`run_child`), the child serves the task
(`serve`) and prints its answer as JSON; what a task needs beyond its arguments it reads as
JSON from its standard input. The ends of a child:

- `UNPROCESSABLE`: the file cannot be used; the child printed the reason as JSON.
- Out of memory (PDFium aborts, Python raises MemoryError; killed by the kernel) or out of time
  (`LEKTO_PDF_TIMEOUT`): `pdf_too_complex`. Neither is tried again: the same file needs as much
  the next time.
- Ended by another signal: PDFium crashed on the file, which cannot be read.
- Any other end is an error of Lekto's (RuntimeError), which the node tries again.
"""

import json
import signal
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta

from lekto.adapters.outbound.system import run_process
from lekto.core.domain.errors import UnprocessableDocumentError, ValidationError
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.reasons import Reason, ReasonCode, because

DEFAULT_TIMEOUT = timedelta(minutes=10)
"""The time a child may take (`LEKTO_PDF_TIMEOUT`): the code reader and the page renderer take
0.1 to 0.2 s a page, a PDF of 1000 pages two minutes on a fast machine."""
UNPROCESSABLE = 3
OUT_OF_MEMORY = 4
_OUT_OF_MEMORY_SIGNALS = (-signal.SIGABRT, -signal.SIGKILL)

type Task = Callable[[Sequence[str], JsonValue], JsonValue]


async def run_child(
    module: str,
    task: str,
    args: Sequence[str],
    *,
    timeout: timedelta,
    memory: int | None,
    input: JsonValue = None,
) -> JsonValue:
    """The answer of `task` with `args` (and `input` on its standard input) in a child running
    `module`. UnprocessableDocumentError for a file the child cannot use (see the module)."""
    try:
        completed = await run_process(
            [sys.executable, "-m", module, task, *args],
            timeout=timeout,
            memory=memory,
            input=None if input is None else json.dumps(input).encode(),
        )
    except TimeoutError:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_TOO_COMPLEX)) from None
    code = completed.returncode
    if code == 0:
        try:
            answer: JsonValue = json.loads(completed.stdout)
        except ValueError:
            raise RuntimeError(f"{task} gave no usable answer") from None
        return answer
    if code == UNPROCESSABLE:
        try:
            reason = Reason.from_json(json.loads(completed.stdout))
        except (ValueError, ValidationError):
            raise RuntimeError(f"{task} gave no usable reason") from None
        raise UnprocessableDocumentError(reason)
    if code == OUT_OF_MEMORY or code in _OUT_OF_MEMORY_SIGNALS:
        raise UnprocessableDocumentError(because(ReasonCode.PDF_TOO_COMPLEX))
    if code < 0:
        detail = f"PDFium ended with {signal.Signals(-code).name}"
        raise UnprocessableDocumentError(because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=detail))
    last = completed.stderr.strip().rsplit("\n", 1)[-1]
    raise RuntimeError(f"{task} failed with exit code {code}: {last}")


def serve(module: str, tasks: Mapping[str, Task], argv: Sequence[str]) -> int:
    """The child's side: run the task `argv[0]` of `tasks` with the rest of `argv` and the
    JSON of the standard input, print its answer; the exit code (see the module)."""
    if not argv or argv[0] not in tasks:
        print(f"usage: python -m {module} {{{','.join(tasks)}}} ARGS...", file=sys.stderr)
        return 2
    try:
        given = sys.stdin.read()
        answer = tasks[argv[0]](argv[1:], json.loads(given) if given else None)
    except UnprocessableDocumentError as error:
        json.dump(error.reason.to_json(), sys.stdout)
        return UNPROCESSABLE
    except MemoryError:
        return OUT_OF_MEMORY
    json.dump(answer, sys.stdout)
    return 0
