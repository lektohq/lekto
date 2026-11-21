import { describe, expect, it } from 'vitest';
import {
	apiQuery,
	isFiltered,
	monthPeriod,
	NO_FILTERS,
	parseFilters,
	periodOf,
	writeFilters,
	yearPeriod
} from './filters.ts';

describe('filters in the URL', () => {
	it('reads and writes all of them', () => {
		const params = new URLSearchParams(
			'contact=c1&contact=c2&type=t1&tag=a&tag=b&contact_group=g1&type_group=g2&type_group=g3' +
				'&space=d1&lane=red&lane=bogus&field=f1&topic=p1&topic=p2&date_from=2026-09-01' +
				'&date_to=2026-09-30&q=x&fact=invoice_number:4711:refers&fact=::own'
		);
		const filters = parseFilters(params);
		expect(filters).toEqual({
			contacts: ['c1', 'c2'],
			types: ['t1'],
			tags: ['a', 'b'],
			contactGroups: ['g1'],
			typeGroups: ['g2', 'g3'],
			topics: ['p1', 'p2'],
			spaces: ['d1'],
			field: 'f1',
			dateFrom: '2026-09-01',
			dateTo: '2026-09-30',
			period: null,
			facts: ['invoice_number:4711:refers', '::own']
		});
		// The archive has no lanes; an older link's lane narrows nothing.
		expect(apiQuery(filters)).not.toHaveProperty('lane');
		const out = writeFilters(new URLSearchParams('q=x&tag=old&contact_group=old'), filters);
		expect(out.getAll('contact')).toEqual(['c1', 'c2']);
		expect(out.getAll('tag')).toEqual(['a', 'b']);
		expect(out.getAll('contact_group')).toEqual(['g1']);
		expect(out.getAll('type_group')).toEqual(['g2', 'g3']);
		expect(out.get('date_from')).toBe('2026-09-01');
		// Several contacts, types, spaces or topics: one of them.
		expect(apiQuery(filters).contact_id).toEqual(['c1', 'c2']);
		expect(apiQuery(filters).document_type_id).toEqual(['t1']);
		expect(apiQuery(filters).space_id).toEqual(['d1']);
		expect(apiQuery(filters).contact_group_id).toEqual(['g1']);
		expect(apiQuery(filters).document_type_group_id).toEqual(['g2', 'g3']);
		expect(out.getAll('topic')).toEqual(['p1', 'p2']);
		expect(apiQuery(filters).topic_id).toEqual(['p1', 'p2']);
		expect(apiQuery(filters).document_date_from).toBe('2026-09-01');
		expect(apiQuery(filters).document_date_to).toBe('2026-09-30');
		expect(out.get('q')).toBe('x');
		// Facts: all of them.
		expect(out.getAll('fact')).toEqual(['invoice_number:4711:refers', '::own']);
		expect(apiQuery(filters).fact).toEqual(['invoice_number:4711:refers', '::own']);
		// Whom the list covers is a setting, not part of the link.
		expect(out.has('all')).toBe(false);
		expect(apiQuery(filters, true).all_users).toBe(true);
		expect(apiQuery(filters).all_users).toBeUndefined();
	});

	it('takes a value given twice once, in the order it first came', () => {
		const params = new URLSearchParams(
			'contact=c1&contact=c2&contact=c1&tag=t1&tag=t1&type=y1&type=y1&space=s1&space=s1' +
				'&contact_group=g1&contact_group=g1&type_group=h1&type_group=h1&topic=o1&topic=o1' +
				'&fact=iban%3Ar1%3A&fact=iban%3Ar1%3A'
		);
		expect(parseFilters(params)).toEqual({
			...NO_FILTERS,
			contacts: ['c1', 'c2'],
			tags: ['t1'],
			types: ['y1'],
			spaces: ['s1'],
			contactGroups: ['g1'],
			typeGroups: ['h1'],
			topics: ['o1'],
			facts: ['iban:r1:']
		});
	});

	it('leaves out what is not set, and a day that is none', () => {
		expect(writeFilters(new URLSearchParams(), NO_FILTERS).toString()).toBe('');
		expect(apiQuery(NO_FILTERS)).toEqual({
			contact_id: undefined,
			document_type_id: undefined,
			tag_id: undefined,
			contact_group_id: undefined,
			document_type_group_id: undefined,
			topic_id: undefined,
			space_id: undefined,
			field_id: undefined,
			document_date_from: undefined,
			document_date_to: undefined,
			fact: undefined,
			all_users: undefined
		});
		expect(parseFilters(new URLSearchParams('date_from=gestern')).dateFrom).toBeNull();
		expect(parseFilters(new URLSearchParams('contact_group=&contact=c1&field='))).toEqual({
			...NO_FILTERS,
			contacts: ['c1']
		});
		expect(isFiltered(NO_FILTERS)).toBe(false);
		expect(isFiltered({ ...NO_FILTERS, tags: ['a'] })).toBe(true);
		expect(isFiltered({ ...NO_FILTERS, contacts: ['c1'] })).toBe(true);
		expect(isFiltered({ ...NO_FILTERS, field: 'f1' })).toBe(true);
		expect(isFiltered({ ...NO_FILTERS, typeGroups: ['g1'] })).toBe(true);
		expect(isFiltered({ ...NO_FILTERS, topics: ['p1'] })).toBe(true);
		expect(isFiltered({ ...NO_FILTERS, dateTo: '2026-01-01' })).toBe(true);
	});

	it('reads a quick pick as its days of today, and writes it by its name (WG-03)', () => {
		const today = new Date(2026, 10, 21);
		const read = parseFilters(new URLSearchParams('period=last_year'), today);
		expect(read).toMatchObject({
			dateFrom: '2025-01-01',
			dateTo: '2025-12-31',
			period: 'last_year'
		});
		// It moves with the day: the same address a year later.
		expect(
			parseFilters(new URLSearchParams('period=last_year'), new Date(2027, 0, 1))
		).toMatchObject({ dateFrom: '2026-01-01', dateTo: '2026-12-31' });
		expect(writeFilters(new URLSearchParams('date_from=2020-01-01'), read).toString()).toBe(
			'period=last_year'
		);
		// The same days chosen as such stay days.
		const days = parseFilters(
			new URLSearchParams('date_from=2025-01-01&date_to=2025-12-31'),
			today
		);
		expect(days.period).toBeNull();
		expect(writeFilters(new URLSearchParams('period=last_year'), days).toString()).toBe(
			'date_from=2025-01-01&date_to=2025-12-31'
		);
		// The quick pick counts before days beside it; an unknown one is none.
		expect(
			parseFilters(new URLSearchParams('period=this_year&date_from=2020-01-01'), today).dateFrom
		).toBe('2026-01-01');
		expect(parseFilters(new URLSearchParams('period=next_year'), today)).toMatchObject({
			dateFrom: null,
			period: null
		});
	});
});

describe('the period of the document date', () => {
	it('is a whole year, a whole month or a span', () => {
		expect(yearPeriod(2026)).toEqual({ dateFrom: '2026-01-01', dateTo: '2026-12-31' });
		expect(monthPeriod('2026-02')).toEqual({ dateFrom: '2026-02-01', dateTo: '2026-02-28' });
		expect(monthPeriod('2024-02').dateTo).toBe('2024-02-29');
		expect(periodOf(yearPeriod(2026))).toEqual({ kind: 'year', year: 2026 });
		expect(periodOf(monthPeriod('2026-09'))).toEqual({ kind: 'month', month: '2026-09' });
		expect(periodOf({ dateFrom: '2026-09-02', dateTo: null })).toEqual({
			kind: 'span',
			from: '2026-09-02',
			to: null
		});
		expect(periodOf({ dateFrom: null, dateTo: null })).toBeNull();
	});
});
