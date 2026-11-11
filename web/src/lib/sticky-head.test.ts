import { describe, expect, it } from 'vitest';
import { aside, SLACK, type Aside } from '#lib/sticky-head.ts';

const run = (start: Aside, ...steps: [number, boolean][]) =>
	steps.reduce((state, [y, stuck]) => aside(state, y, stuck), start);

describe('the row that steps aside', () => {
	it('stays while it scrolls with the page, before it stands at the top', () => {
		expect(run({ hidden: false, anchor: 0 }, [40, false], [120, false])).toEqual({
			hidden: false,
			anchor: 120
		});
	});

	it('steps aside scrolling down at the top, and comes back scrolling up', () => {
		const down = run({ hidden: false, anchor: 200 }, [204, true], [200 + SLACK + 1, true]);
		expect(down.hidden).toBe(true);
		const further = run(down, [600, true], [597, true]);
		expect(further).toEqual({ hidden: true, anchor: 600 });
		expect(aside(further, 600 - SLACK - 1, true).hidden).toBe(false);
	});

	it('comes back where it scrolls with the page again', () => {
		expect(aside({ hidden: true, anchor: 900 }, 100, false).hidden).toBe(false);
	});

	it('does not shake for a few pixels', () => {
		const shown = run({ hidden: false, anchor: 300 }, [303, true], [298, true], [302, true]);
		expect(shown.hidden).toBe(false);
	});
});
