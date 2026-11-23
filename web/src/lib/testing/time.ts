/**
 * Time in tests without waiting a fixed while (WT1-K16, WT2-K01, WT3-K03): what a component does
 * after a delay is brought about with fake timers (`fakeTime`, `elapse`); what follows an answer
 * is waited for until the answers settled (`settled`).
 */

import { expect, onTestFinished, vi, type Mock } from 'vitest';

/** Fake timers for this test, `Date` and `performance` with them, so that what measures time
 * sees it pass; real again when the test ends. Once faked, `@testing-library`'s `waitFor` and
 * `findBy…` wait on the fake clock: wait with `vi.waitFor`, and set `userEvent` up with
 * `advanceTimers: vi.advanceTimersByTime`. */
export function fakeTime(): void {
	vi.useFakeTimers({
		toFake: [
			'setTimeout',
			'clearTimeout',
			'setInterval',
			'clearInterval',
			'requestAnimationFrame',
			'cancelAnimationFrame',
			'Date',
			'performance'
		]
	});
	onTestFinished(() => {
		vi.useRealTimers();
	});
}

/** Let `ms` pass on the fake clock: what falls due runs, and the promises it starts. */
export async function elapse(ms: number): Promise<void> {
	await vi.advanceTimersByTimeAsync(ms);
}

/** Every call of `mock` (the faked fetch, unless another is named) has its answer, and what the
 * answers started ran: their promise chains and Svelte's updates, one turn of the event loop
 * after the last. For a check that a late answer, or none, changes nothing; real timers only. */
export async function settled(mock?: Mock): Promise<void> {
	const fake = mock ?? globalThis.fetch;
	if (vi.isMockFunction(fake)) {
		await vi.waitFor(() =>
			expect(fake.mock.settledResults.some((result) => result.type === 'incomplete')).toBe(false)
		);
	}
	await new Promise((resolve) => setTimeout(resolve, 0));
}
