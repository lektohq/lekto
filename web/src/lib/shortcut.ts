/**
 * The shortcut for iPhone, iPad and Mac (web/DESIGN.md, "App"; Tobi, 06.11.2026): "An Lekto
 * senden" sends the files shared with it to `POST /documents` with a token of the scope `upload`:
 * PDFs, images and files; a photo in HEIC (the iPhone's) it turns into a JPEG first.
 * On adding it, the Shortcuts app asks for the token first, then for Lekto's address. Its link
 * comes from the server (`LEKTO_SHORTCUT_URL`, `session.shortcutUrl`); without one the web UI
 * shows nothing of the shortcut. A new version of the shortcut comes with a new link.
 */
export const SHORTCUT_NAME = 'An Lekto senden';

/** Lekto's address as the shortcut wants it: without a slash at the end. */
export function lektoAddress(origin: string): string {
	return origin.replace(/\/+$/, '');
}
