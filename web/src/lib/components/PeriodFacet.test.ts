import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { QUICK_PICKS } from '#lib/period-label.ts';
import PeriodFacet from './PeriodFacet.svelte';

afterEach(() => vi.useRealTimers());

describe('PeriodFacet', () => {
	it('picks "last year" by the day it is clicked, not the day it opened (WC-K20)', async () => {
		vi.useFakeTimers({ toFake: ['Date'] });
		vi.setSystemTime(new Date(2026, 11, 31, 23, 59));
		const onchange = vi.fn();
		render(PeriodFacet, {
			years: [],
			undated: 0,
			period: { dateFrom: null, dateTo: null, period: null },
			showCounts: false,
			onchange
		});
		vi.setSystemTime(new Date(2027, 0, 1, 0, 1)); // past midnight, a new year
		await fireEvent.click(screen.getByRole('button', { name: QUICK_PICKS.last_year() }));
		expect(onchange).toHaveBeenCalledWith({
			dateFrom: '2026-01-01',
			dateTo: '2026-12-31',
			period: 'last_year'
		});
	});
});
