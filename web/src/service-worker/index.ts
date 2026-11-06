// The service worker of the installed app (web/DESIGN.md, "App"). It keeps the files of one
// version of the app, so that the app starts without a connection, and nothing else: what the
// API answers never lands on the device (`lib/app-cache.ts`). A new version waits until the
// person reloads (`lib/app-update.ts`).

import { version } from '$app/env';
import { assets } from '$app/manifest';
import { self as worker } from '$app/service-worker';
import { appFiles, pageFiles, pageKey, shellPaths, strategy } from '#lib/app-cache.ts';
import { BASE as base } from '#lib/base.ts';

const CACHE = `lekto-${version}`;
const PAGE = pageKey(base);
// The small files of `static/`; PDF.js's decoders, fonts and maps come from the network.
const SHELL = new Set(
	shellPaths(
		assets.map((file) => file.path),
		base
	)
);

worker.addEventListener('install', (event) => {
	event.waitUntil(
		(async () => {
			const cache = await caches.open(CACHE);
			const page = await fetch(PAGE, { cache: 'no-cache' });
			if (!page.ok) throw new Error(`the app's page answered ${page.status}`);
			const html = await page.clone().text();
			await cache.put(PAGE, page);
			await cache.addAll([...SHELL, ...pageFiles(html, base)]);
		})()
	);
});

worker.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			for (const key of await caches.keys()) {
				if (key !== CACHE && key.startsWith('lekto-')) await caches.delete(key);
			}
			// The first version takes the open pages over at once, so that what they load from
			// now on is kept; a later one comes only when the person reloads.
			await worker.clients.claim();
		})()
	);
});

worker.addEventListener('message', (event) => {
	const data = event.data as { type?: string; urls?: string[] } | null;
	if (data?.type === 'version') {
		event.ports[0]?.postMessage({ version });
	} else if (data?.type === 'skip-waiting') {
		void worker.skipWaiting();
	} else if (data?.type === 'keep' && Array.isArray(data.urls)) {
		event.waitUntil(keep(appFiles(data.urls, worker.location.origin, base)));
	}
});

/** Keep the files of the app the page loaded before this worker was in control. */
async function keep(paths: string[]): Promise<void> {
	const cache = await caches.open(CACHE);
	for (const path of paths) {
		if (await cache.match(path)) continue;
		try {
			const response = await fetch(path);
			if (response.ok) await cache.put(path, response);
		} catch {
			// Offline again: the next start tries anew.
		}
	}
}

worker.addEventListener('fetch', (event) => {
	const request = event.request;
	switch (strategy(request, worker.location.origin, base, SHELL)) {
		case 'file':
			event.respondWith(file(request));
			break;
		case 'page':
			event.respondWith(page(request));
			break;
		case 'network':
			// Not handled: the browser fetches it as if there were no service worker.
			break;
	}
});

async function file(request: Request): Promise<Response> {
	const cache = await caches.open(CACHE);
	const kept = await cache.match(request);
	if (kept) return kept;
	const response = await fetch(request);
	if (response.ok) await cache.put(request, response.clone());
	return response;
}

async function page(request: Request): Promise<Response> {
	try {
		return await fetch(request);
	} catch (error) {
		const kept = await (await caches.open(CACHE)).match(PAGE);
		if (kept) return kept;
		throw error;
	}
}
