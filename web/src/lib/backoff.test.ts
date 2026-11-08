import { describe, expect, it } from 'vitest';
import { RETRY_FIRST_MS, RETRY_MAX_MS, retryDelay } from '#lib/backoff.ts';

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
