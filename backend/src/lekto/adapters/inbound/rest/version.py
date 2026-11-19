"""The version of the REST API (Tobi, 19.11.2026, `.knowledge/open/api-version-fas.md`): its own,
apart from Lekto's release, so that a client knows whether it still fits.

`MAJOR.MINOR`: MAJOR rises with a change that breaks a client (a pull request with the label
`breaking-change`), MINOR with one that only adds. The path stays `/api/v1` during the beta.
`FINGERPRINT` is the SHA-256 of the OpenAPI document without its texts and examples
(`tests/unit/test_api_version.py`): a test fails while the API changed and the version did not.
"""

API_VERSION = "1.0"
FINGERPRINT = "66882812f5772418fbaeb2d441d325da3c2c149955c7bbad26019e3ad5c64d43"
