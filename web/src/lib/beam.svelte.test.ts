import { afterEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { goTo, testPage } from '#lib/testing/page-state.svelte.ts';
import {
	beamCount,
	beamTo,
	closeBeam,
	leaveBeam,
	openBeam,
	partsOf,
	showPages
} from './beam.svelte.ts';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

afterEach(() => {
	vi.mocked(goto).mockClear();
	vi.restoreAllMocks();
	goTo('/ui/inbox');
});

describe('the state of the Beam', () => {
	it('opens in a new history entry beside what the entry holds, each document once', () => {
		goTo('/ui/documents', {}, { words: 'Strom' });
		openBeam(['a', 'b', 'a', 'c'], 'c', 'Dokumente');
		expect(goto).toHaveBeenCalledWith('http://lekto/ui/documents', {
			shallow: true,
			state: { words: 'Strom', beam: { ids: ['a', 'b', 'c'], index: 2, from: 'Dokumente' } },
			persistState: true
		});
	});

	it('pages in the same entry, and closes by going back to the entry before', () => {
		const back = vi.spyOn(history, 'back').mockImplementation(() => {});
		goTo('/ui/documents');
		openBeam(['a', 'b'], 'a', 'Dokumente');
		testPage.state = { beam: { ids: ['a', 'b'], index: 0, from: 'Dokumente' } };
		beamTo(1);
		expect(vi.mocked(goto).mock.lastCall?.[1]).toMatchObject({ replace: true });
		beamTo(2); // beyond the last: nothing
		expect(goto).toHaveBeenCalledTimes(2);
		closeBeam();
		expect(back).toHaveBeenCalledOnce();
	});

	it('shows the parts of an edit by a key, their images never in the history entry', () => {
		goTo('/ui/documents');
		const parts = [
			{ title: 'Teil 1', meta: 'S. 1–2', pages: [{ src: 'data:image/webp;base64,AA==' }] },
			{
				title: 'Teil 2',
				meta: 'S. 3',
				pages: [{ src: '/api/v1/documents/a/pages/3', turn: 90 as const }]
			}
		];
		showPages(parts, 1, 'PDF bearbeiten', 1);
		const state = vi.mocked(goto).mock.lastCall?.[1]?.state as { beam: { parts: string } };
		expect(state.beam).toMatchObject({ ids: [], index: 1, page: 1, from: 'PDF bearbeiten' });
		expect(JSON.stringify(state)).not.toContain('data:');
		expect(partsOf(state.beam.parts)).toBe(parts);
		const beam = { ids: [], parts: state.beam.parts, index: 1, from: 'PDF bearbeiten' };
		expect(beamCount(beam)).toBe(2);
		testPage.state = { beam };
		beamTo(0);
		expect(vi.mocked(goto).mock.lastCall?.[1]?.state).toMatchObject({ beam: { index: 0 } });
		// Another edit's parts take the place of these: the older key names nothing.
		showPages(parts.slice(0, 1), 0, 'PDF bearbeiten');
		expect(partsOf(state.beam.parts)).toBeNull();
	});

	it('shows parts where the browser offers no random ids (plain http in a network)', () => {
		vi.stubGlobal('crypto', {});
		goTo('/ui/documents');
		showPages([{ title: 'Teil 1', meta: 'S. 1', pages: [] }], 0, 'PDF bearbeiten');
		const state = vi.mocked(goto).mock.lastCall?.[1]?.state as { beam: { parts: string } };
		expect(partsOf(state.beam.parts)).toHaveLength(1);
		vi.unstubAllGlobals();
		leaveBeam();
	});

	it('lets a jump take the entry it opened in, not one a reload restored', () => {
		goTo('/ui/documents');
		openBeam(['a'], 'a', 'Dokumente');
		testPage.state = { beam: { ids: ['a'], index: 0, from: 'Dokumente' } };
		expect(leaveBeam()).toBe(true);
		// Left once: the entry is gone, a second jump does not take another.
		expect(leaveBeam()).toBe(false);
		goTo('/ui/documents', {}, { beam: { ids: ['a'], index: 0, from: 'Dokumente' } });
		expect(leaveBeam()).toBe(false);
	});
});
