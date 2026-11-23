import { belongsTo, SHARED_CACHE } from '#lib/app-cache.ts';
import { BASE } from '#lib/base.ts';

/**
 * The files another app shared with the installed one (web/DESIGN.md, "App"), as the service
 * worker keeps them under the share's id. Reading leaves them where they are: any website can
 * post files to the share target, so the page `/share` shows them and asks before anything is
 * uploaded. A file leaves the device once its upload has a result (`forgetSharedFile`), a
 * share the person discards at once (`forgetShared`); what failed stays to be tried again,
 * until the worker removes the share after its hour.
 */

/** Where a file read from a share lies on the device, to remove that one alone. */
const PLACES = new WeakMap<File, { cache: Cache; request: Request }>();

async function kept(id: string): Promise<{ cache: Cache; requests: Request[] } | null> {
	if (!('caches' in window)) return null;
	const cache = await caches.open(SHARED_CACHE);
	const requests = (await cache.keys())
		.map((request) => ({ request, path: new URL(request.url).pathname }))
		.filter(({ path }) => belongsTo(path, BASE, id))
		.sort((a, b) => Number(a.path.split('/').pop()) - Number(b.path.split('/').pop()))
		.map(({ request }) => request);
	return { cache, requests };
}

/** The files of a share, in the order they came; none for a share that is gone. */
export async function readShared(id: string): Promise<File[]> {
	const found = await kept(id);
	if (!found) return [];
	const files: File[] = [];
	for (const request of found.requests) {
		const response = await found.cache.match(request);
		if (!response) continue;
		const blob = await response.blob();
		const name = decodeURIComponent(response.headers.get('x-lekto-name') ?? 'file');
		const file = new File([blob], name, { type: blob.type });
		PLACES.set(file, { cache: found.cache, request });
		files.push(file);
	}
	return files;
}

/** Remove one file of a share from the device: its upload has a result. Nothing for a file
 * that was not read from a share. */
export async function forgetSharedFile(file: File): Promise<void> {
	const place = PLACES.get(file);
	if (place) await place.cache.delete(place.request);
}

/** Remove a share from the device: the person discarded it. */
export async function forgetShared(id: string): Promise<void> {
	const found = await kept(id);
	if (!found) return;
	await Promise.all(found.requests.map((request) => found.cache.delete(request)));
}
