"""`python -m lekto.adapters.outbound.zxing codes PDF PAGES`: the codes on the first `PAGES`
pages of a PDF (`all`: every page), read in a process of its own with the limits its parent
sets (`pdfium.child`)."""

import sys

from lekto.adapters.outbound.pdfium.child import serve
from lekto.adapters.outbound.zxing.reader import MODULE, codes_task

if __name__ == "__main__":
    sys.exit(serve(MODULE, {"codes": codes_task}, sys.argv[1:]))
