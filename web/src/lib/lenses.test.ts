import { describe, expect, it } from 'vitest';
import { NO_FILTERS, parseFilters, quickPick, relativePeriod, yearPeriod } from './filters.ts';
import {
	lensDiffers,
	lensFilter,
	lensFilters,
	lensParams,
	rememberLensFacts,
	type Lens
} from './lenses.ts';
import { factFilterLabel } from './facts.ts';

const TODAY = new Date(2026, 9, 20); // 20 October 2026
const EMPTY: Lens['filter'] = {
	contact_ids: [],
	document_type_ids: [],
	contact_group_ids: [],
	document_type_group_ids: [],
	topic_ids: [],
	tag_ids: [],
	space_ids: [],
	field_id: null,
	document_date_from: null,
	document_date_to: null,
	document_period: null,
	facts: []
};

function lens(
	parts: Omit<Partial<Lens>, 'filter'> & { filter?: Partial<Lens['filter']> } = {}
): Lens {
	const { filter, ...rest } = parts;
	return {
		id: 'l1',
		name: 'To pay',
		position: 0,
		query: null,
		sort: null,
		sort_field_id: null,
		grouping: 'none',
		layout: 'grid',
		card_field_ids: [],
		due_field_id: null,
		created_at: '2026-10-20T10:00:00Z',
		updated_at: '2026-10-20T10:00:00Z',
		...rest,
		filter: { ...EMPTY, ...filter }
	};
}

describe('periods that move with the day', () => {
	it('are this year, the last twelve months up to today and last year', () => {
		expect(relativePeriod('this_year', TODAY)).toEqual({
			dateFrom: '2026-01-01',
			dateTo: '2026-12-31'
		});
		expect(relativePeriod('last_12_months', TODAY)).toEqual({
			dateFrom: '2025-10-21',
			dateTo: null
		});
		expect(relativePeriod('last_year', TODAY)).toEqual({
			dateFrom: '2025-01-01',
			dateTo: '2025-12-31'
		});
	});
});

describe('a lens in the URL', () => {
	it('opens with its filters and sort, a moving period by its name', () => {
		const opened = lensParams(
			lens({
				filter: { tag_ids: ['t1', 't2'], document_period: 'this_year', field_id: 'f2' },
				sort: '-field',
				sort_field_id: 'f1'
			}),
			TODAY
		);
		expect(opened.toString()).toBe(
			'lens=l1&tag=t1&tag=t2&field=f2&period=this_year&sort=-field&sort_field=f1'
		);
		// The page reads the days of today from it.
		expect(parseFilters(opened, TODAY)).toMatchObject({
			dateFrom: '2026-01-01',
			dateTo: '2026-12-31',
			period: 'this_year'
		});
		// Its words go into the history entry, never into the URL.
		const searched = lensParams(lens({ query: 'power bill', sort: 'relevance' }), TODAY);
		expect(searched.toString()).toBe('lens=l1&sort=relevance');
		expect(lensFilters(lens({ filter: { document_date_from: '2024-05-01' } }), TODAY)).toEqual({
			...NO_FILTERS,
			dateFrom: '2024-05-01'
		});
	});

	it('is saved from the filters, a quick pick as such', () => {
		const filters = { ...NO_FILTERS, contacts: ['c1'], ...quickPick('last_year', TODAY) };
		expect(lensFilter(filters)).toMatchObject({
			contact_ids: ['c1'],
			document_period: 'last_year',
			document_date_from: null,
			document_date_to: null
		});
		const fixed = { ...NO_FILTERS, dateFrom: '2024-01-01', dateTo: '2024-12-31' };
		expect(lensFilter(fixed)).toMatchObject({
			document_period: null,
			document_date_from: '2024-01-01',
			document_date_to: '2024-12-31'
		});
	});

	it('keeps a year chosen as such, though it is last year today (WG-03)', () => {
		// The tile "2025" gives the days of "last year" in 2026; a lens of them must not show
		// 2026 from the first of January on.
		const year = { ...NO_FILTERS, ...yearPeriod(TODAY.getFullYear() - 1) };
		expect(lensFilter(year)).toMatchObject({
			document_period: null,
			document_date_from: '2025-01-01',
			document_date_to: '2025-12-31'
		});
		// And a lens kept so stays so when it is opened and saved again.
		const kept = lens({
			filter: { document_date_from: '2025-01-01', document_date_to: '2025-12-31' }
		});
		const opened = lensParams(kept, TODAY);
		expect(opened.toString()).toBe('lens=l1&date_from=2025-01-01&date_to=2025-12-31');
		expect(lensFilter(parseFilters(opened, TODAY)).document_period).toBeNull();
		expect(lensDiffers(kept, opened, '', TODAY)).toBe(false);
		// The quick pick of the same days is another choice.
		const moving = new URLSearchParams('lens=l1&period=last_year');
		expect(lensDiffers(kept, moving, '', TODAY)).toBe(true);
	});
});

describe('the facts of a lens', () => {
	it('go to the URL and come back as the lens keeps them', () => {
		const kept = lens({
			filter: {
				facts: [
					{ kind: 'invoice_number', value: 'R1001', ref: 'Zm9v', role: null },
					{ kind: null, value: null, ref: null, role: 'refers' }
				]
			}
		});
		const opened = lensParams(kept, TODAY);
		// The value by its reference, never as written.
		expect(opened.getAll('fact')).toEqual(['invoice_number:Zm9v:', '::refers']);
		expect(lensFilter(lensFilters(kept, TODAY)).facts).toEqual([
			{ kind: 'invoice_number', ref: 'Zm9v', role: null },
			{ kind: null, ref: null, role: 'refers' }
		]);
		rememberLensFacts([kept]);
		expect(factFilterLabel('invoice_number:Zm9v:')).toContain('R1001');
	});
});

describe('a page and its lens', () => {
	it('differ in filters, words or sort, not in the order of repeated values', () => {
		const open = lens({ filter: { tag_ids: ['t1', 't2'] }, sort: 'title' });
		const same = new URLSearchParams('lens=l1&sort=title&tag=t2&tag=t1');
		expect(lensDiffers(open, same, '', TODAY)).toBe(false);
		expect(lensDiffers(open, same, 'power', TODAY)).toBe(true);
		expect(lensDiffers({ ...open, query: 'power' }, same, 'power', TODAY)).toBe(false);
		for (const other of [
			'lens=l1&sort=title&tag=t1',
			'lens=l1&sort=title&tag=t1&tag=t2&contact=c1',
			'lens=l1&tag=t1&tag=t2'
		]) {
			expect(lensDiffers(open, new URLSearchParams(other), '', TODAY)).toBe(true);
		}
		const moving = lens({ filter: { document_period: 'this_year' } });
		expect(lensDiffers(moving, new URLSearchParams('lens=l1&period=this_year'), '', TODAY)).toBe(
			false
		);
		// Its days of today chosen as such are a fixed year, another choice.
		expect(
			lensDiffers(
				moving,
				new URLSearchParams('lens=l1&date_from=2026-01-01&date_to=2026-12-31'),
				'',
				TODAY
			)
		).toBe(true);
	});
});
