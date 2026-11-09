import { describe, expect, it } from 'vitest';
import { SummaryPager } from '#lib/summary-pager.svelte.ts';

/** A promise and the hand that settles it. */
function later<T>() {
	let settle!: (value: T) => void;
	const promise = new Promise<T>((resolve) => (settle = resolve));
	return { promise, settle };
}

describe('a log with its summary', () => {
	it('keeps the summary of the latest page asked for, not one that comes late', async () => {
		const answers = [later<string>(), later<string>()];
		let call = 0;
		const log = new SummaryPager<{ id: string }, string>(async () => {
			const summary = await answers[call++].promise;
			return { items: [{ id: summary }], total: 1, summary };
		}, 25);
		const first = log.pager.go(1);
		const second = log.pager.go(1);
		answers[1].settle('newer');
		await second;
		answers[0].settle('older');
		await first;
		expect(log.summary).toBe('newer');
		expect(log.pager.items).toEqual([{ id: 'newer' }]);
	});

	it('forgets the summary when it starts over', async () => {
		const log = new SummaryPager<{ id: string }, string>(
			async () => ({ items: [], total: 0, summary: 'counted' }),
			25
		);
		await log.pager.go(1);
		expect(log.summary).toBe('counted');
		const pending = log.reset();
		expect(log.summary).toBeNull();
		await pending;
		expect(log.summary).toBe('counted');
	});
});
