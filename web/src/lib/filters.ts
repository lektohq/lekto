/**
 * The filters of the document view (list and search), as they stand in the page's URL. No lane:
 * where a document stands is the inbox's matter (the API keeps the filter).
 */
import { isIsoDay, isoDayLocal, lastDayOfMonth, pad2 } from '#lib/dates.ts';

export interface Filters {
	/** One of them (each repeats in the URL). */
	contacts: string[];
	types: string[];
	/** Each with the tags below it; all of them. */
	tags: string[];
	/** Documents whose contact (type) is in each group or one below it. */
	contactGroups: string[];
	typeGroups: string[];
	/** Documents with one of these topics or one below it (a document has one topic). */
	topics: string[];
	/** One of them. */
	spaces: string[];
	/** Documents with a value for this field. */
	field: string | null;
	/** The document date lies between them, both days included (ISO days; either open). */
	dateFrom: string | null;
	dateTo: string | null;
	/** A quick pick of the period, which moves with the day ("last year"); `dateFrom` and
	 * `dateTo` then hold its days as of today. Null: the days are meant as they stand, also
	 * when they are the days of a quick pick today (the tile of a year). */
	period: RelativePeriod | null;
	/** Facts the document has, each as `kind:value:role` (any part empty for any); all. */
	facts: string[];
}

export const NO_FILTERS: Filters = {
	contacts: [],
	types: [],
	tags: [],
	contactGroups: [],
	typeGroups: [],
	topics: [],
	spaces: [],
	field: null,
	dateFrom: null,
	dateTo: null,
	period: null,
	facts: []
};

const LISTS = {
	contacts: 'contact',
	types: 'type',
	tags: 'tag',
	contactGroups: 'contact_group',
	typeGroups: 'type_group',
	topics: 'topic',
	spaces: 'space'
} as const;

/** The filters in `params`; empty values (`?contact=`) count as none, a value given twice
 * (`?contact=c1&contact=c1`, in a link written by hand) once: each value is one chip, and a list
 * names it once. Whom the list covers is no filter but a setting (`scope`). A quick pick of
 * the period stands as its name (`period=last_year`) and means its days as of `today`; it
 * counts before days beside it. */
export function parseFilters(params: URLSearchParams, today: Date = new Date()): Filters {
	const all = (key: string) => [...new Set(params.getAll(key).filter((value) => value !== ''))];
	const period = RELATIVE_PERIODS.find((known) => known === params.get('period')) ?? null;
	const days = period
		? relativePeriod(period, today)
		: { dateFrom: day(params.get('date_from')), dateTo: day(params.get('date_to')) };
	return {
		contacts: all(LISTS.contacts),
		types: all(LISTS.types),
		tags: all(LISTS.tags),
		contactGroups: all(LISTS.contactGroups),
		typeGroups: all(LISTS.typeGroups),
		topics: all(LISTS.topics),
		spaces: all(LISTS.spaces),
		field: params.get('field') || null,
		...days,
		period,
		facts: all('fact')
	};
}

/** Write the filters into `params` (other parameters stay). */
export function writeFilters(params: URLSearchParams, filters: Filters): URLSearchParams {
	for (const key of [...Object.values(LISTS), 'field', 'date_from', 'date_to', 'period', 'fact']) {
		params.delete(key);
	}
	for (const [list, key] of Object.entries(LISTS) as [keyof typeof LISTS, string][]) {
		for (const id of filters[list]) params.append(key, id);
	}
	if (filters.field) params.set('field', filters.field);
	if (filters.period) {
		params.set('period', filters.period);
	} else {
		if (filters.dateFrom) params.set('date_from', filters.dateFrom);
		if (filters.dateTo) params.set('date_to', filters.dateTo);
	}
	for (const fact of filters.facts) params.append('fact', fact);
	return params;
}

/** The query of the API for these filters; `allUsers` from the scope setting. */
export function apiQuery(filters: Filters, allUsers = false) {
	const list = (ids: string[]) => (ids.length > 0 ? ids : undefined);
	return {
		contact_id: list(filters.contacts),
		document_type_id: list(filters.types),
		tag_id: list(filters.tags),
		contact_group_id: list(filters.contactGroups),
		document_type_group_id: list(filters.typeGroups),
		topic_id: list(filters.topics),
		space_id: list(filters.spaces),
		field_id: filters.field ?? undefined,
		document_date_from: filters.dateFrom ?? undefined,
		document_date_to: filters.dateTo ?? undefined,
		fact: list(filters.facts),
		all_users: allUsers || undefined
	};
}

/** Whether a filter narrows the list. */
export function isFiltered(filters: Filters): boolean {
	return Boolean(
		filters.field ||
		filters.dateFrom ||
		filters.dateTo ||
		filters.facts.length > 0 ||
		Object.keys(LISTS).some((list) => filters[list as keyof typeof LISTS].length > 0)
	);
}

/** A whole year or month of the document date, as the filters hold it. */
export function yearPeriod(year: number): Pick<Filters, 'dateFrom' | 'dateTo'> {
	return { dateFrom: `${year}-01-01`, dateTo: `${year}-12-31` };
}

/** `month` as `2026-09`. */
export function monthPeriod(month: string): Pick<Filters, 'dateFrom' | 'dateTo'> {
	const [year, number] = month.split('-').map(Number);
	return { dateFrom: `${month}-01`, dateTo: `${month}-${pad2(lastDayOfMonth(year, number))}` };
}

/** A period that moves with the day: the quick picks of the filters, as the address and a lens
 * keep them. */
export type RelativePeriod = 'this_year' | 'last_12_months' | 'last_year';
export const RELATIVE_PERIODS: readonly RelativePeriod[] = [
	'this_year',
	'last_12_months',
	'last_year'
];

/** The days of `period` as of `today`: this or last year, or the twelve months up to today. */
export function relativePeriod(
	period: RelativePeriod,
	today: Date
): Pick<Filters, 'dateFrom' | 'dateTo'> {
	const year = today.getFullYear();
	switch (period) {
		case 'this_year':
			return yearPeriod(year);
		case 'last_year':
			return yearPeriod(year - 1);
		case 'last_12_months': {
			// The day after the same day a year before, the 28th of February for the 29th: as the
			// core reckons it (`RelativePeriod.period`), which a lens's numbers and MCP use (WT3-05).
			const day = Math.min(today.getDate(), lastDayOfMonth(year - 1, today.getMonth() + 1));
			const start = new Date(year - 1, today.getMonth(), day + 1);
			return { dateFrom: isoDayLocal(start), dateTo: null };
		}
	}
}

/** The filters with a quick pick as their period: its name and its days as of `today`. */
export function quickPick(
	period: RelativePeriod,
	today: Date
): Pick<Filters, 'dateFrom' | 'dateTo' | 'period'> {
	return { ...relativePeriod(period, today), period };
}

/** What the period of the filters is: a whole year, a whole month, another span, or none. */
export type PeriodChoice =
	| { kind: 'year'; year: number }
	| { kind: 'month'; month: string }
	| { kind: 'span'; from: string | null; to: string | null }
	| null;

export function periodOf(filters: Pick<Filters, 'dateFrom' | 'dateTo'>): PeriodChoice {
	const { dateFrom: from, dateTo: to } = filters;
	if (!from && !to) return null;
	if (from && to) {
		const year = Number(from.slice(0, 4));
		const whole = yearPeriod(year);
		if (whole.dateFrom === from && whole.dateTo === to) return { kind: 'year', year };
		const month = monthPeriod(from.slice(0, 7));
		if (month.dateFrom === from && month.dateTo === to) {
			return { kind: 'month', month: from.slice(0, 7) };
		}
	}
	return { kind: 'span', from, to };
}

/** An ISO day, or null for anything else. */
function day(value: string | null): string | null {
	return value && isIsoDay(value) ? value : null;
}
