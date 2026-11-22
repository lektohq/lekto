import { describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { listedOf } from '#lib/testing/documents.ts';
import { calls, fakeApi } from '#lib/testing/api.ts';
import { listPlaces, SEARCH_PAGE_MAX } from './list-places.ts';

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
				score: null,
				snippet: []
			}));
		const api = fakeApi({
			'POST /api/v1/documents/search': (_, url) =>
				({
					items: page(Number(url.searchParams.get('offset'))),
					estimated_total: 5000,
					word_total: 5000,
					next_offset: null,
					semantic: false,
					mode: 'words',
					reason: null,
					meaning_pending: false
				}) satisfies components['schemas']['SearchResultPage']
		});
		vi.stubGlobal('fetch', api);
		const ids = await listPlaces('/ui/documents?tag=t1', 'Strom', false);
		expect(ids).toHaveLength(200);
		expect(ids[150]).toBe('d150');
		// The filters and the sort of the list, page by page (WT3-06: the request was not read).
		expect(calls(api)).toEqual([
			'POST /api/v1/documents/search?tag_id=t1&sort=relevance&offset=0&limit=100',
			'POST /api/v1/documents/search?tag_id=t1&sort=relevance&offset=100&limit=100'
		]);
		const sent = await Promise.all(api.mock.calls.map(([request]) => request.clone().json()));
		expect(sent).toEqual([{ q: 'Strom' }, { q: 'Strom' }]);
	});
});
