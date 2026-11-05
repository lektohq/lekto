"""`python -m lekto.adapters.outbound.weasyprint LOCALE MAIL TARGET`: set the mail `MAIL` as the
PDF `TARGET`, in a process of its own; `WeasyPrintMailRenderer` runs it with a time limit.
Prints what it set as JSON (`pages`, `renderer`, `pdfa`); exits with `NO_MAIL` if the file is no
mail."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from lekto.adapters.outbound.weasyprint.renderer import NO_MAIL, set_mail
from lekto.core.domain.errors import UnprocessableDocumentError


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: python -m lekto.adapters.outbound.weasyprint LOCALE MAIL TARGET",
            file=sys.stderr,
        )
        return 2
    locale, mail, target = argv
    try:
        rendered = set_mail(Path(mail), Path(target), locale)
    except UnprocessableDocumentError:
        return NO_MAIL
    json.dump(asdict(rendered), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
