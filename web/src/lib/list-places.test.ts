import { afterEach, describe, expect, it, vi } from 'vitest';
import { listedOf } from '#lib/testing/documents.ts';
import { calls, fakeApi } from '#lib/testing/api.ts';
import { listPlaces, SEARCH_PAGE_MAX } from './list-places.ts';

afterEach(() => vi.unstubAllGlobals());

describe('the documents of the list a document was opened from', () => {
	it('reads the list page by page, with its filters, sort and selection', async () => {
		const api = fakeApi({
			'GET /api/v1/documents': (_, url) =>
				url.searchParams.get('cursor') === 'next'
					? { items: [listedOf({ id: 'c' })], next_cursor: null }
					: { items: [listedOf({ id: 'a' }), listedOf({ id: 'b' })], next_cursor: 'next' }
		});
		vi.stubGlobal('fetch', api);
		expect(await listPlaces('/ui/documents?contact=k1&sort=title&page=3', '', true)).toEqual([
			'a',
			'b',
			'c'
		]);
		expect(calls(api)).toEqual([
			'GET /api/v1/documents?contact_id=k1&all_users=true&sort=title&limit=200',
			'GET /api/v1/documents?contact_id=k1&all_users=true&sort=title&limit=200&cursor=next'
		]);
	});

	it('reads the hits of a search, as far as it looks', async () => {
		const page = (offset: number) =>
			Array.from({ length: SEARCH_PAGE_MAX }, (_, n) => ({
				document: listedOf({ id: `d${offset + n}` }),
				snippet: []
			}));
		const api = fakeApi({
			'POST /api/v1/documents/search': (_, url) => ({
				items: page(Number(url.searchParams.get('offset'))),
				estimated_total: 5000,
				word_total: 5000,
				mode: 'words'
			})
		});
		vi.stubGlobal('fetch', api);
		const ids = await listPlaces('/ui/documents?tag=t1', 'Strom', false);
		expect(ids).toHaveLength(200);
		expect(ids[150]).toBe('d150');
		expect(calls(api)).toHaveLength(2);
	});
});
