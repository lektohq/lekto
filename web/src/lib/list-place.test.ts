import { afterEach, describe, expect, it, vi } from 'vitest';
import { ListPlace } from './list-place.svelte.ts';
import { returnTo } from './return-to.svelte.ts';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

afterEach(() => vi.unstubAllGlobals());

describe('the place in a list', () => {
	it('is gone to once, when the list says it stands', async () => {
		const scrollTo = vi.fn();
		vi.stubGlobal('scrollTo', scrollTo);
		const place = new ListPlace();
		await place.reach();
		expect(scrollTo).not.toHaveBeenCalled();
		place.want({ y: 1500, loaded: 60 });
		expect(place.wanted).toEqual({ y: 1500, loaded: 60 });
		await place.reach();
		await place.reach();
		expect(scrollTo.mock.calls).toEqual([[0, 1500]]);
		expect(place.wanted).toBeNull();
	});

	it('takes nothing else for a place: a history entry may be older', () => {
		const place = new ListPlace();
		for (const other of [undefined, null, 1500, 'top', {}, { y: '12' }, { y: Number.NaN }]) {
			place.want(other);
			expect(place.wanted).toBeNull();
		}
		place.want({ y: 0, loaded: 'many' });
		expect(place.wanted).toEqual({ y: 0, loaded: undefined });
	});

	it('goes with the way back from a document, for each list its own', () => {
		expect(returnTo.inboxState).toEqual({});
		expect(returnTo.state).not.toHaveProperty('place');
		returnTo.rememberPlace('documents', { y: 1500 });
		returnTo.rememberPlace('inbox', { y: 900, loaded: 60 });
		expect(returnTo.state.place).toEqual({ y: 1500 });
		expect(returnTo.inboxState).toEqual({ place: { y: 900, loaded: 60 } });
	});
});
