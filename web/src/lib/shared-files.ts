import { belongsTo, SHARED_CACHE } from '#lib/app-cache.ts';
import { BASE } from '#lib/base.ts';

/**
 * The files another app shared with the installed one (web/DESIGN.md, "App"), as the service
 * worker keeps them under the share's id. Reading leaves them where they are: any website can
 * post files to the share target, so the page `/share` shows them and asks before anything is
 * uploaded (`forgetShared` once the person has decided).
 */

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
		files.push(new File([blob], name, { type: blob.type }));
	}
	return files;
}

/** Remove a share from the device: its files are with the upload, or the person discarded them. */
export async function forgetShared(id: string): Promise<void> {
	const found = await kept(id);
	if (!found) return;
	await Promise.all(found.requests.map((request) => found.cache.delete(request)));
}
