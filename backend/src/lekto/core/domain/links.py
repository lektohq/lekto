"""Where Lekto's own pages and endpoints are, for what the core hands out: the answer address
and the file links of a task, the link to a document in a template, where a notification
leads (review 0.12.2, C-05).

The core knows the paths below the two prefixes; the prefixes and the public address come from
the composition (the REST adapter's `PREFIX`, the web UI's `UI_PREFIX`, `LEKTO_PUBLIC_URL`),
so that a renamed prefix reaches every link at once."""

from dataclasses import dataclass

# Below the API's prefix.
TASKS = "/external/tasks/"
TASK_RESULT = TASKS + "{id}/result"
TASK_FILE = TASKS + "{id}/files/{name}"
# Below the web UI's prefix.
HOME = "/"
DOCUMENT = "/documents/{id}"
INBOX = "/inbox"
NOTIFICATIONS = "/settings?tab=notifications"
MAILBOX = "/system/mailboxes/{id}"
WEBHOOK = "/webhooks/{id}"
JOBS = "/system?tab=jobs"


@dataclass(frozen=True)
class Links:
    """`public`: `LEKTO_PUBLIC_URL` (None: no absolute link can be given); `api_prefix` and
    `ui_prefix` where the API and the web UI stand below it."""

    public: str | None
    api_prefix: str
    ui_prefix: str

    def api(self, path: str) -> str | None:
        """The absolute address of an API path (`TASK_RESULT` …); None without a public URL."""
        return None if self.public is None else self.public.rstrip("/") + self.api_prefix + path

    def ui(self, path: str) -> str:
        """A page of the web UI as a path of this server (where a notification leads)."""
        return self.ui_prefix + path

    def ui_absolute(self, path: str) -> str | None:
        """A page of the web UI as an absolute address (a template's `link`); None without a
        public URL."""
        return None if self.public is None else self.public.rstrip("/") + self.ui(path)
