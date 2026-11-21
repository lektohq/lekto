import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SHARED_CACHE, sharedKey } from '#lib/app-cache.ts';
import { BASE } from '#lib/base.ts';
import { forgetShared, readShared } from '#lib/shared-files.ts';

const ID = '0b0e7c1e-2f2a-4d67-9a43-6f1f0c2d9e11';
const OTHER = '1c1f8d2f-3a3b-4e78-8b54-7a2a1d3e0f22';

/** The part of the Cache API the shares use, kept in a map. */
function fakeCaches() {
	const kept = new Map<string, Response>();
	const cache = {
		keys: async () => [...kept.keys()].map((url) => new Request(url)),
		match: async (request: Request) => kept.get(request.url)?.clone(),
		delete: async (request: Request) => kept.delete(request.url)
	};
	return {
		kept,
		caches: { open: vi.fn(async () => cache) }
	};
}

describe('the files of a share', () => {
	let kept: Map<string, Response>;

	const keep = (id: string, index: number, name: string) =>
		kept.set(
			`http://localhost${sharedKey(BASE, id, index)}`,
			new Response(name, {
				headers: { 'content-type': 'application/pdf', 'x-lekto-name': encodeURIComponent(name) }
			})
		);

	beforeEach(() => {
		const fake = fakeCaches();
		kept = fake.kept;
		vi.stubGlobal('caches', fake.caches);
	});

	it('are read in the order they came, with their names and kinds', async () => {
		keep(ID, 10, 'elf.pdf');
		keep(ID, 2, 'Größe 3 ä.pdf');
		keep(ID, 0, 'eins.pdf');

		const files = await readShared(ID);

		expect(files.map((file) => file.name)).toEqual(['eins.pdf', 'Größe 3 ä.pdf', 'elf.pdf']);
		expect(files[0].type).toBe('application/pdf');
		expect(caches.open).toHaveBeenCalledWith(SHARED_CACHE);
	});

	it('stay on the device when read: a share opened again is still there', async () => {
		keep(ID, 0, 'eins.pdf');

		await readShared(ID);

		expect(await readShared(ID)).toHaveLength(1);
		expect(kept.size).toBe(1);
	});

	it('leave the device when forgotten, those of another share stay', async () => {
		keep(ID, 0, 'eins.pdf');
		keep(ID, 1, 'zwei.pdf');
		keep(OTHER, 0, 'fremd.pdf');

		await forgetShared(ID);

		expect(await readShared(ID)).toEqual([]);
		expect((await readShared(OTHER)).map((file) => file.name)).toEqual(['fremd.pdf']);
	});

	it('are none without the Cache API', async () => {
		vi.unstubAllGlobals();

		expect(await readShared(ID)).toEqual([]);
		await expect(forgetShared(ID)).resolves.toBeUndefined();
	});
});
