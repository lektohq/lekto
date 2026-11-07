import { belongsTo, SHARED_CACHE } from '#lib/app-cache.ts';
import { BASE } from '#lib/base.ts';

/**
 * The files another app shared with the installed one (web/DESIGN.md, "App"), as the service
 * worker keeps them under the share's id: taken out of its cache, in the order they came. What is
 * taken is gone from the device; a share opened twice is empty the second time.
 */
export async function takeShared(id: string): Promise<File[]> {
	if (!('caches' in window)) return [];
	const cache = await caches.open(SHARED_CACHE);
	const requests = (await cache.keys())
		.map((request) => ({ request, path: new URL(request.url).pathname }))
		.filter(({ path }) => belongsTo(path, BASE, id))
		.sort((a, b) => Number(a.path.split('/').pop()) - Number(b.path.split('/').pop()));
	const files: File[] = [];
	for (const { request } of requests) {
		const response = await cache.match(request);
		if (response) {
			const blob = await response.blob();
			const name = decodeURIComponent(response.headers.get('x-lekto-name') ?? 'file');
			files.push(new File([blob], name, { type: blob.type }));
		}
		await cache.delete(request);
	}
	return files;
}
