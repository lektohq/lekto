import { periodOf, type Filters, type RelativePeriod } from '#lib/filters.ts';
import { formatDate } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';

/** The name of each quick pick of the period. */
export const QUICK_PICKS: Record<RelativePeriod, () => string> = {
	this_year: m.facet_this_year,
	last_12_months: m.facet_last_12_months,
	last_year: m.facet_last_year
};

/** The period of the filters in words: a quick pick by its name ("Letztes Jahr": it moves with
 * the day), else `2026`, `September 2026`, `from …`, `… to …`; null for none. */
export function periodLabel(
	filters: Pick<Filters, 'dateFrom' | 'dateTo'> & Partial<Pick<Filters, 'period'>>
): string | null {
	if (filters.period) return QUICK_PICKS[filters.period]();
	const period = periodOf(filters);
	if (period === null) return null;
	if (period.kind === 'year') return String(period.year);
	if (period.kind === 'month') {
		return formatDate(new Date(`${period.month}-01T00:00:00`), { month: 'long', year: 'numeric' });
	}
	const day = (value: string) => formatDate(new Date(`${value}T00:00:00`), { dateStyle: 'medium' });
	if (period.from && period.to)
		return m.period_span({ from: day(period.from), to: day(period.to) });
	return period.from
		? m.period_from({ date: day(period.from) })
		: m.period_to({ date: day(period.to ?? '') });
}
