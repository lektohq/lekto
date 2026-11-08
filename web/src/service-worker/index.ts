// The service worker of the installed app (web/DESIGN.md, "App"). It keeps the files of one
// version of the app, so that the app starts without a connection, and nothing else: what the
// API answers never lands on the device (`lib/app-cache.ts`). A new version waits until the
// person reloads (`lib/app-update.ts`).

import { version } from '$app/env';
import { assets } from '$app/manifest';
import { self as worker } from '$app/service-worker';
import {
	appFiles,
	pageFiles,
	pageKey,
	SHARED_CACHE,
	SHARED_FOR_MS,
	sharedKey,
	sharePath,
	shellPaths,
	strategy
} from '#lib/app-cache.ts';
import { BASE as base } from '#lib/base.ts';
import { type PushPayload, pushText } from '#lib/push-text.ts';

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
				if (key !== CACHE && key !== SHARED_CACHE && key.startsWith('lekto-')) {
					await caches.delete(key);
				}
			}
			await forgetOldShares();
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
		case 'share':
			event.respondWith(share(request));
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

/** Files another app shared (Android's share sheet, the manifest's `share_target`): kept under a
 * random id until the page `<base>/share` uploads them, at most an hour. */
async function share(request: Request): Promise<Response> {
	const form = await request.formData();
	const files = form.getAll('files').filter((item): item is File => item instanceof File);
	const id = crypto.randomUUID();
	const cache = await caches.open(SHARED_CACHE);
	const now = String(Date.now());
	await Promise.all(
		files.map((file, index) =>
			cache.put(
				sharedKey(base, id, index),
				new Response(file, {
					headers: {
						'content-type': file.type || 'application/octet-stream',
						'x-lekto-name': encodeURIComponent(file.name),
						'x-lekto-kept': now
					}
				})
			)
		)
	);
	await forgetOldShares();
	return Response.redirect(`${sharePath(base)}?id=${id}`, 303);
}

async function forgetOldShares(): Promise<void> {
	const cache = await caches.open(SHARED_CACHE);
	for (const request of await cache.keys()) {
		const kept = Number((await cache.match(request))?.headers.get('x-lekto-kept') ?? 0);
		if (Date.now() - kept > SHARED_FOR_MS) await cache.delete(request);
	}
}

/** A notification from Lekto (`services.push`): data, worded in the device's language. On
 * iPhone and iPad every push must show one; the app's icon gets the number of the inbox. */
worker.addEventListener('push', (event) => {
	event.waitUntil(show(event.data));
});

async function show(data: PushMessageData | null): Promise<void> {
	let payload: PushPayload;
	try {
		payload = data?.json() as PushPayload;
	} catch {
		payload = { kind: 'test', params: {}, url: `${base}/`, badge: null, tag: null, locale: 'en' };
	}
	const { title, body } = pushText(payload);
	const badge = payload.badge;
	const navigator = worker.navigator as WorkerNavigator & {
		setAppBadge?: (count?: number) => Promise<void>;
		clearAppBadge?: () => Promise<void>;
	};
	if (typeof badge === 'number') {
		await (badge > 0 ? navigator.setAppBadge?.(badge) : navigator.clearAppBadge?.())?.catch(
			() => undefined
		);
	}
	await worker.registration.showNotification(title, {
		body,
		tag: payload.tag ?? undefined,
		icon: `${base}/icon-192.png`,
		data: { url: payload.url }
	});
}

/** A tap opens what it is about: in an open window of the app, else a new one. */
worker.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const target = new URL(
		String((event.notification.data as { url?: string } | null)?.url ?? `${base}/`),
		worker.location.origin
	);
	if (target.origin !== worker.location.origin) return;
	event.waitUntil(open(target.href));
});

async function open(url: string): Promise<void> {
	const windows = await worker.clients.matchAll({ type: 'window', includeUncontrolled: true });
	const app = windows.find((client) => new URL(client.url).pathname.startsWith(`${base}/`));
	if (app) {
		await app.focus();
		await app.navigate(url).catch(() => undefined);
	} else {
		await worker.clients.openWindow(url);
	}
}
