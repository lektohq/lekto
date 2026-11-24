"""Whether a release's migration client speaks the release's API (`.github/workflows/release.yml`).

    python3 .github/scripts/pylekto_api.py

pylekto X.Y.Z speaks Lekto's API X.Y, and it is released before the Lekto release whose API it
speaks, so that release's `lekto-migration` brings the client of its own API. Prints a warning
for GitHub Actions (`::warning::`) when the pylekto in `migration/uv.lock` speaks another API
than `API_VERSION`; the release goes on (a stop would leave a published release without images).
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_MODULE = ROOT / "backend/src/lekto/adapters/inbound/rest/version.py"
MIGRATION_LOCK = ROOT / "migration/uv.lock"

_API_VERSION = re.compile(r'^API_VERSION = "(?P<version>[^"]+)"$', re.MULTILINE)


def api_version(module: str) -> str:
    """The `API_VERSION` of the REST adapter's `version.py`."""
    found = _API_VERSION.search(module)
    if found is None:
        raise ValueError("no API_VERSION in version.py")
    return found["version"]


def pylekto_version(lock: str) -> str:
    """The version of pylekto locked in a `uv.lock`."""
    for package in tomllib.loads(lock).get("package", []):
        if package.get("name") == "pylekto":
            return str(package["version"])
    raise ValueError("no pylekto in uv.lock")


def mismatch(api: str, pylekto: str) -> str | None:
    """Why the pylekto `pylekto` does not speak the API `api`; None if it does."""
    spoken = ".".join(pylekto.split(".")[:2])
    if spoken == api:
        return None
    return (
        f"lekto-migration brings pylekto {pylekto} (API {spoken}), this release speaks the API "
        f"{api}: release the pylekto of the API {api} first, then raise its pin"
    )


def main() -> int:
    why = mismatch(
        api_version(VERSION_MODULE.read_text(encoding="utf-8")),
        pylekto_version(MIGRATION_LOCK.read_text(encoding="utf-8")),
    )
    print(f"::warning::{why}" if why else "pylekto speaks this release's API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
