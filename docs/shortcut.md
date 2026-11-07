# Shortcut for iPhone, iPad and Mac

Safari cannot put a web app into the share menu. The shortcut **"An Lekto senden"** does it
instead: share a document from any app, and it uploads it to Lekto. On the Mac it also stands in
the share menu of every app and, in the Finder, under right-click › Quick Actions.

## Set it up

The operator names the shortcut's link in `LEKTO_SHORTCUT_URL` (`docs/configuration.md`; the
Compose examples' `.env.example` carries the current one). Without it, Lekto shows nothing of the
shortcut.

1. Open Lekto on the device (Safari, or the app on the Home Screen) and go to
   **Settings › API-Tokens**. On iPhone, iPad and Mac the card **"Kurzbefehl für iPhone, iPad und
   Mac"** stands first.
2. Tap **Einrichten**. Lekto creates a token named "Kurzbefehl · iPhone" (iPad, Mac) that may
   only upload documents, and shows it with Lekto's address. The token is shown only once.
3. Tap **Zu Kurzbefehle hinzufügen**. The Shortcuts app opens and asks two questions when you add
   the shortcut:
   - first **the token**: copy it in Lekto (1 · Token) and paste it;
   - then **the Lekto URL**: copy it in Lekto (2 · Lekto-URL) and paste it, without a `/` at the
     end.
4. Done. The card now says **Eingerichtet**.

Set up every device on its own, each with its own token: **Weiteres Gerät einrichten** creates the
next one.

## What it does

It takes PDFs, images and files (scans from the Files app, mails as `.eml`). A photo in HEIC, as the
iPhone takes them, it turns into a JPEG first: Lekto reads JPEG, PNG and TIFF. For every file, the
shortcut sends `POST <URL>/api/v1/documents` with the file in the form field `file` and the token
as `Authorization: Bearer`. Then:

- **"An Lekto gesendet"**: the document is in Lekto; the shortcut opens it (in Safari: iOS opens
  links there, not in the app on the Home Screen, so you may have to sign in there).
- **"Liegt schon in Lekto"**: the same file was uploaded before (`409`); it opens that document.
- **An error**: it shows Lekto's message, for example when the token was revoked.

Uploaded documents go into your personal space and through the inbox, like every upload.

## The token

A token of the scope **upload** ("Nur hochladen") reaches only `POST /api/v1/documents`. It reads
nothing, not even what it uploaded; every other request answers `403` (`upload_only_token`), and
the MCP server refuses it. If a device is lost, revoke its token in **Settings › API-Tokens**:
the shortcut on that device stops working at once.

## Without the shortcut

- **Mail:** send the document to a mailbox Lekto fetches (System › Eingangskanäle › Mail).
- **Upload:** **Hochladen** in the inbox takes files, photos and the camera.
- **Android:** the installed app stands in the share menu itself; no shortcut needed.
