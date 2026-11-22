import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeApi, problem } from '#lib/testing/api.ts';
import { searchTyped, TYPING_PAUSE_MS } from './document-search.ts';

const doc = (id: string, title: string) => ({ id, title });
const RECENT = [doc('a', 'Stromrechnung März'), doc('b', 'Mietvertrag')];

function picker() {
	const shown: ({ id: string; title: string }[] | null)[] = [];
	return {
		shown,
		to: {
			recent: () => RECENT,
			read: (document: { id: string; title: string }) => doc(document.id, document.title),
			show: (found: { id: string; title: string }[] | null) => shown.push(found)
		}
	};
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('the documents a picker finds for what was typed (WA-14)', () => {
	it('asks after a pause and shows the hits', async () => {
		const fetchMock = fakeApi({
			'POST /api/v1/documents/search': () => ({
				items: [{ document: doc('c', 'Stromrechnung April') }]
			})
		});
		vi.stubGlobal('fetch', fetchMock);
		const { shown, to } = picker();
		searchTyped(' Strom ', to);
		expect(fetchMock).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(TYPING_PAUSE_MS);
		await vi.waitFor(() => expect(shown).toEqual([[doc('c', 'Stromrechnung April')]]));
		const request = fetchMock.mock.calls[0][0];
		expect(await request.json()).toEqual({ q: 'Strom' });
		expect(new URL(request.url).searchParams.get('semantic_ratio')).toBe('0');
	});

	it('falls back on the newest ones by their title where the search does not answer', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/documents/search': () => problem(503)
			})
		);
		const { shown, to } = picker();
		searchTyped('miet', to);
		await vi.advanceTimersByTimeAsync(TYPING_PAUSE_MS);
		await vi.waitFor(() => expect(shown).toEqual([[doc('b', 'Mietvertrag')]]));
	});

	it('keeps what was found until the answer, and shows nothing found without a text', async () => {
		const fetchMock = fakeApi({ 'POST /api/v1/documents/search': () => ({ items: [] }) });
		vi.stubGlobal('fetch', fetchMock);
		const { shown, to } = picker();
		// Typing on: nothing is shown anew before the answer, and the earlier key asks nothing.
		const stop = searchTyped('s', to);
		stop?.();
		searchTyped('st', to);
		expect(shown).toEqual([]);
		await vi.advanceTimersByTimeAsync(TYPING_PAUSE_MS);
		await vi.waitFor(() => expect(shown).toEqual([[]]));
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(searchTyped('  ', to)).toBeUndefined();
		expect(shown).toEqual([[], null]);
	});
});
