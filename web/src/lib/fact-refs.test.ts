import { describe, expect, it, vi } from 'vitest';
import { refValue } from '#lib/fact-refs.svelte.ts';
import { fakeApi } from '#lib/testing/api.ts';

describe('the values behind references', () => {
	it('asks again after no answer came, not after a refusal (WG-K10)', async () => {
		let online = false;
		const api = fakeApi({
			'GET /api/v1/identifiers/refs/iban/r1': () => {
				if (!online) throw new TypeError('Failed to fetch');
				return { kind: 'iban', ref: 'r1', value: 'DE89 3704 0044 0532 0130 00' };
			}
		});
		vi.stubGlobal('fetch', api);
		expect(refValue('iban', 'r1')).toBeNull();
		await vi.waitFor(() => expect(api).toHaveBeenCalledTimes(1));
		await new Promise((resolve) => setTimeout(resolve, 0));
		online = true;
		expect(refValue('iban', 'r1')).toBeNull(); // asked again: the first never arrived
		await vi.waitFor(() => expect(refValue('iban', 'r1')).toBe('DE89 3704 0044 0532 0130 00'));
		expect(api).toHaveBeenCalledTimes(2);
	});
});
