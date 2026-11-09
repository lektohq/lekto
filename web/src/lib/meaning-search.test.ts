import { afterEach, describe, expect, it, vi } from 'vitest';
import { calls, fakeApi } from '#lib/testing/api.ts';
import { forgetMeaningSearch, warmSearch } from './meaning-search.ts';

afterEach(() => {
	vi.unstubAllGlobals();
	forgetMeaningSearch();
});

function stub(meaning: boolean) {
	const api = fakeApi({
		'GET /api/v1/pipeline': () => ({
			nodes: [],
			vision: null,
			logo_fetch: false,
			meaning_search: meaning
		})
	});
	vi.stubGlobal('fetch', api);
	return api;
}

const warmed = (api: ReturnType<typeof stub>) =>
	calls(api).filter((call) => call === 'POST /api/v1/documents/search/warm');

describe('warming the search', () => {
	it('asks the API at most once a minute', async () => {
		const fetch = stub(true);
		warmSearch(1_000_000);
		warmSearch(1_030_000);
		warmSearch(1_060_000);
		await vi.waitFor(() => expect(warmed(fetch)).toHaveLength(2));
	});

	it('does nothing without a search by meaning', async () => {
		const fetch = stub(false);
		warmSearch(1_000_000);
		await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
		await new Promise((resolve) => setTimeout(resolve, 10));
		expect(warmed(fetch)).toHaveLength(0);
	});
});
