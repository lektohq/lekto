import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { calls, fakeApi } from '#lib/testing/api.ts';
import { documentOf } from '#lib/testing/documents.ts';
import type { Separation } from '#lib/separation.ts';
import SeparationDetails from './SeparationDetails.svelte';

function looked(splitOff: string[]): Separation {
	return {
		kind: 'looked',
		pages: 4,
		sheets: [3],
		separators: ['PATCH T'],
		codes: [],
		version: 2,
		splitOff
	};
}

describe('SeparationDetails', () => {
	it('asks the parts once, not again for the same parts read anew', async () => {
		const api = fakeApi({
			'GET /api/v1/documents/doc-9': () => documentOf({ id: 'doc-9', title: 'Zweiter Teil' })
		});
		vi.stubGlobal('fetch', api);
		const shown = render(SeparationDetails, { separation: looked(['doc-9']) });
		expect(await screen.findByText('Zweiter Teil')).toBeTruthy();
		// The log read anew gives the same parts in a new list (WA-K05).
		await shown.rerender({ separation: looked(['doc-9']) });
		expect(screen.getByText('Zweiter Teil')).toBeTruthy();
		expect(calls(api)).toEqual(['GET /api/v1/documents/doc-9']);
	});
});
