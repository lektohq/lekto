import { beforeEach, describe, expect, it } from 'vitest';
import {
	forgetRetries,
	nextRetry,
	RETRY_FIRST_MS,
	RETRY_MAX_MS,
	retryDelay
} from '#lib/backoff.ts';

describe('retryDelay', () => {
	it('doubles the wait up to a minute', () => {
		const middle = () => 0.5;
		expect([1, 2, 3, 4, 5, 6, 20].map((failures) => retryDelay(failures, middle))).toEqual([
			5_000, 10_000, 20_000, 40_000, 60_000, 60_000, 60_000
		]);
	});

	it('spreads the wait by a fifth either way', () => {
		expect(retryDelay(1, () => 0)).toBe(RETRY_FIRST_MS * 0.8);
		expect(retryDelay(1, () => 1)).toBe(RETRY_FIRST_MS * 1.2);
		expect(retryDelay(9, () => 1)).toBe(RETRY_MAX_MS * 1.2);
	});
});

describe('nextRetry', () => {
	const middle = () => 0.5;
	beforeEach(forgetRetries);

	it('waits longer each time a server that cannot be reached is asked again', () => {
		let now = 1_000_000;
		const waits = [1, 2, 3, 4, 5, 6].map(() => {
			const wait = nextRetry(now, middle);
			now += wait;
			return wait;
		});
		expect(waits).toEqual([5_000, 10_000, 20_000, 40_000, 60_000, 60_000]);
	});

	it('counts for the whole tab, over a reload too, and starts over after a quiet while', () => {
		expect(nextRetry(1_000_000, middle)).toBe(5_000);
		// Another card of the page, or the page loaded again: the same count.
		expect(JSON.parse(sessionStorage.getItem('lekto.retry') ?? '{}').failures).toBe(1);
		expect(nextRetry(1_005_000, middle)).toBe(10_000);
		// The server was back for a while.
		expect(nextRetry(1_005_000 + 2 * RETRY_MAX_MS + 1, middle)).toBe(5_000);
	});
});
