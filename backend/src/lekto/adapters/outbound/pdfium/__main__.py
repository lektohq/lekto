"""`python -m lekto.adapters.outbound.pdfium TASK ARGS...`: read a PDF with PDFium in a process
of its own, with the limits its parent sets (`child`). The tasks:

- `text-layer PDF`: what its text layer needs from the OCR (`library.read_text_layer`)
- `pages PDF TARGET WIDTH PREVIEW_WIDTH`: its page images (`pages.render`)
- `parse PDF TEXT STRUCTURE`: its text as it is set (`layout.parse`)
- `locate PDF`, the texts as JSON on the standard input: their places (`locator.locate`)
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from lekto.adapters.outbound.pdfium.child import Task, serve
from lekto.adapters.outbound.pdfium.layout import parse_task
from lekto.adapters.outbound.pdfium.library import MODULE, read_text_layer
from lekto.adapters.outbound.pdfium.locator import locate_task
from lekto.adapters.outbound.pdfium.pages import render_task
from lekto.core.domain.json_value import JsonValue


def _text_layer(args: Sequence[str], _: JsonValue) -> JsonValue:
    (pdf,) = args
    layer = read_text_layer(Path(pdf))
    return {"unreadable": layer.unreadable, "hidden": layer.hidden}


TASKS: dict[str, Task] = {
    "text-layer": _text_layer,
    "pages": render_task,
    "parse": parse_task,
    "locate": locate_task,
}

if __name__ == "__main__":
    sys.exit(serve(MODULE, TASKS, sys.argv[1:]))
