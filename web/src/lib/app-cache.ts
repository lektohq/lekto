/**
 * What the service worker (`src/service-worker/index.ts`) does with a request. A pure function, so that
 * the rule of the app (web/DESIGN.md, "App") has a test of its own: nothing the API answers is
 * ever kept on the device, only the files of the app itself.
 *
 * - `network`: to the network, untouched, nothing kept. Every request to the API, every method
 *   but GET, other origins, the version check, PDF.js's decoders and fonts, the service worker.
 * - `file`: a file of the app, from the cache, else from the network and then kept. Files below
 *   `_app/immutable/` carry a hash in their name and never change; the others (`shell`) belong
 *   to one version of the app, whose cache goes with it.
 * - `page`: a page of the app, from the network, so that a reload always gets the newest app;
 *   without a connection the app's page from the cache, which then says it is offline.
 * - `share`: files another app shares with the installed one (the manifest's `share_target`,
 *   `POST <base>/share`): kept until the page `<base>/share` hands them to the upload.
 */
export type Strategy = 'network' | 'file' | 'page' | 'share';

export interface RequestLike {
	url: string;
	method: string;
	mode: string;
}

/** The address under which the app's page is kept (the API answers it with `index.html`). */
export function pageKey(base: string): string {
	return `${base}/`;
}

export function strategy(
	request: RequestLike,
	origin: string,
	base: string,
	shell: ReadonlySet<string>
): Strategy {
	const url = new URL(request.url);
	if (url.origin !== origin) return 'network';
	const path = url.pathname;
	if (request.method === 'POST' && path === sharePath(base)) return 'share';
	if (request.method !== 'GET') return 'network';
	if (path === '/api' || path.startsWith('/api/')) return 'network';
	if (path !== base && !path.startsWith(`${base}/`)) return 'network';
	if (request.mode === 'navigate') return 'page';
	if (path.startsWith(`${base}/_app/immutable/`)) return 'file';
	if (shell.has(path)) return 'file';
	return 'network';
}

/** The addresses of the files of `static/` the worker keeps (`$app/manifest`'s `assets`, given
 * relative to the base), without PDF.js's decoders, fonts and maps. */
export function shellPaths(assets: readonly string[], base: string): string[] {
	return assets
		.map((path) => `${base}/${path.replace(/^\/+/, '')}`)
		.filter((path) => !path.startsWith(`${base}/pdfjs/`));
}

/** The files the page loads before anything else (`modulepreload`, style sheets): kept when the
 * app is installed, so that it starts without a connection. */
export function pageFiles(html: string, base: string): string[] {
	const found = new Set<string>();
	for (const match of html.matchAll(/<link\b[^>]*\bhref="([^"]+)"[^>]*>/g)) {
		const href = match[1];
		if (href.startsWith(`${base}/_app/immutable/`)) found.add(href);
	}
	return [...found];
}

/** The files of the app among loaded addresses (`performance` entries of the page): the page
 * hands them to the service worker once it is in control, so that what loaded before is kept
 * too. */
export function appFiles(urls: readonly string[], origin: string, base: string): string[] {
	const found = new Set<string>();
	for (const href of urls) {
		let url: URL;
		try {
			url = new URL(href);
		} catch {
			continue;
		}
		if (url.origin === origin && url.pathname.startsWith(`${base}/_app/immutable/`)) {
			found.add(url.pathname);
		}
	}
	return [...found];
}

/** Shared files wait in their own cache, not in the one of a version: an update in between
 * keeps them. */
export const SHARED_CACHE = 'lekto-shared';

/** How long shared files wait for the page that uploads them. */
export const SHARED_FOR_MS = 60 * 60 * 1000;

/** The share target's address, and the page that takes the files over. */
export function sharePath(base: string): string {
	return `${base}/share`;
}

/** A share's id: random, it names nothing (web/DESIGN.md, "No plain data in addresses"). */
export function isShareId(id: string | null): id is string {
	return id !== null && /^[0-9a-f-]{36}$/.test(id);
}

/** The address under which the `index`-th file of a share is kept. */
export function sharedKey(base: string, id: string, index: number): string {
	return `${sharePath(base)}/${id}/${index}`;
}

/** Whether a kept address belongs to a share. */
export function belongsTo(path: string, base: string, id: string): boolean {
	return path.startsWith(`${sharePath(base)}/${id}/`);
}
