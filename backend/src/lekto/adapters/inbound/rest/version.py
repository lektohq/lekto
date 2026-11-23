"""The version of the REST API (Tobi, 19.11.2026, `.knowledge/open/api-version-fas.md`): its own,
apart from Lekto's release, so that a client knows whether it still fits.

`MAJOR.MINOR`. During the beta MAJOR is 0 and every change of the API raises MINOR, whether it
breaks a client or only adds (Tobi, 19.11.2026): a client takes any other MINOR as possibly
breaking. From the first release without beta the version starts at 1.0; then MAJOR rises with a
change that breaks a client (a pull request with the label `breaking-change`), MINOR with one
that only adds. The path stays `/api/v1` during the beta.
`FINGERPRINT` is the SHA-256 of the OpenAPI document without its texts and examples
(`tests/unit/test_api_version.py`): a test fails while the API changed and the version did not.
"""

API_VERSION = "0.8"
FINGERPRINT = "d704b74a6cdc97e5cb837a5911c0470d0893a3150124f9652b52ed50ee5f2730"
