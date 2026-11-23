import { afterEach, describe, expect, it } from 'vitest';
import { NO_FILTERS } from './filters.ts';
import {
	byMonth,
	filtersCollapsed,
	monthOf,
	forgetFilters,
	rememberFilters,
	rememberFiltersCollapsed,
	rememberSort,
	rememberLayout,
	rememberedFilters,
	rememberedLayout,
	sortFieldOf,
	sortOf
} from './listing.ts';
import { withoutStorage } from '#lib/testing/browser.ts';

afterEach(() => localStorage.clear());

describe('the sort of the document view', () => {
	it('defaults to relevance for a search and to the newest document date for a list', () => {
		expect(sortOf(new URLSearchParams(), true)).toBe('relevance');
		expect(sortOf(new URLSearchParams(), false)).toBe('-document_date');
	});

	it('takes the URL first, then what this browser chose, each for a list or a search', () => {
		rememberSort('title', false);
		rememberSort('-created_at', true);
		expect(sortOf(new URLSearchParams(), false)).toBe('title');
		expect(sortOf(new URLSearchParams(), true)).toBe('-created_at');
		expect(sortOf(new URLSearchParams('sort=document_date'), false)).toBe('document_date');
		// Relevance only where something is searched; nonsense counts as missing.
		expect(sortOf(new URLSearchParams('sort=relevance'), false)).toBe('title');
		expect(sortOf(new URLSearchParams('sort=size'), true)).toBe('-created_at');
	});

	it('sorts a list by a field named in the URL, never a search, and does not remember it', () => {
		const byDue = new URLSearchParams('sort=field&sort_field=f1');
		expect(sortOf(byDue, false)).toBe('field');
		expect(sortFieldOf(byDue, false)).toBe('f1');
		expect(sortOf(new URLSearchParams('sort=-field&sort_field=f1'), false)).toBe('-field');
		// Without the field, or while searching, it counts as missing.
		expect(sortOf(new URLSearchParams('sort=field'), false)).toBe('-document_date');
		expect(sortOf(byDue, true)).toBe('relevance');
		expect(sortFieldOf(byDue, true)).toBeNull();
		expect(sortFieldOf(new URLSearchParams('sort=title&sort_field=f1'), false)).toBeNull();
		rememberSort('field', false);
		expect(sortOf(new URLSearchParams(), false)).toBe('-document_date');
	});

	it('remembers grid or list, grid at first', () => {
		expect(rememberedLayout()).toBe('grid');
		rememberLayout('list');
		expect(rememberedLayout()).toBe('list');
	});
});

describe('the filters the document view remembers', () => {
	it('keeps the filters as set, and forgets them once none is left', () => {
		expect(rememberedFilters('u1')).toBeNull();
		rememberFilters({ ...NO_FILTERS, contacts: ['c1', 'c2'], dateFrom: '2026-01-01' }, 'u1');
		expect(rememberedFilters('u1')).toEqual({
			...NO_FILTERS,
			contacts: ['c1', 'c2'],
			dateFrom: '2026-01-01'
		});
		rememberFilters(NO_FILTERS, 'u1');
		expect(rememberedFilters('u1')).toBeNull();
		expect(localStorage.getItem('lekto.documents.filters')).toBeNull();
	});

	it('counts what was stored but narrows nothing as none', () => {
		localStorage.setItem(
			'lekto.documents.filters',
			JSON.stringify({ user: 'u1', filters: 'contact=&date_from=yesterday' })
		);
		expect(rememberedFilters('u1')).toBeNull();
	});

	it('keeps them for the user who set them: another user gets none', () => {
		rememberFilters({ ...NO_FILTERS, contacts: ['c1'] }, 'u1');
		expect(rememberedFilters('u2')).toBeNull();
		expect(rememberedFilters(undefined)).toBeNull();
		// Still there for their owner.
		expect(rememberedFilters('u1')).toEqual({ ...NO_FILTERS, contacts: ['c1'] });
		// Whoever sets filters next takes the place.
		rememberFilters({ ...NO_FILTERS, tags: ['t1'] }, 'u2');
		expect(rememberedFilters('u1')).toBeNull();
	});

	it('reads a value kept twice once: such a filter once broke the list for good', () => {
		localStorage.setItem(
			'lekto.documents.filters',
			JSON.stringify({
				user: 'u1',
				filters: 'contact=c1&contact=c1&fact=iban%3Ar%3A&fact=iban%3Ar%3A'
			})
		);
		expect(rememberedFilters('u1')).toEqual({
			...NO_FILTERS,
			contacts: ['c1'],
			facts: ['iban:r:']
		});
	});

	it('remembers none without a user', () => {
		rememberFilters({ ...NO_FILTERS, contacts: ['c1'] }, undefined);
		expect(localStorage.getItem('lekto.documents.filters')).toBeNull();
	});

	it("takes filters kept without their user as no one's", () => {
		// As this browser kept them before they named their user.
		localStorage.setItem('lekto.documents.filters', 'contact=c1');
		expect(rememberedFilters('u1')).toBeNull();
		localStorage.setItem('lekto.documents.filters', JSON.stringify({ filters: 'contact=c1' }));
		expect(rememberedFilters('u1')).toBeNull();
		localStorage.setItem('lekto.documents.filters', 'null');
		expect(rememberedFilters('u1')).toBeNull();
	});

	it('forgets them on demand', () => {
		rememberFilters({ ...NO_FILTERS, contacts: ['c1'] }, 'u1');
		forgetFilters();
		expect(rememberedFilters('u1')).toBeNull();
		expect(localStorage.getItem('lekto.documents.filters')).toBeNull();
	});

	it('remembers the panel collapsed, open at first', () => {
		expect(filtersCollapsed()).toBe(false);
		rememberFiltersCollapsed(true);
		expect(filtersCollapsed()).toBe(true);
		rememberFiltersCollapsed(false);
		expect(filtersCollapsed()).toBe(false);
		expect(localStorage.getItem('lekto.documents.filters-collapsed')).toBeNull();
	});

	it('works without storage: nothing remembered, nothing thrown', () => {
		withoutStorage(() => {
			expect(() => rememberFilters({ ...NO_FILTERS, contacts: ['c1'] }, 'u1')).not.toThrow();
			expect(rememberedFilters('u1')).toBeNull();
			expect(() => rememberFiltersCollapsed(true)).not.toThrow();
			expect(filtersCollapsed()).toBe(false);
		});
	});
});

describe('the months of the document view', () => {
	const doc = (document_date: string | null, created_at = '2026-10-18T08:00:00') => ({
		document_date,
		created_at
	});

	it('groups a sort by date by month, and nothing else', () => {
		expect(monthOf('-document_date', doc('2026-09-30'))).toBe('2026-09');
		expect(monthOf('document_date', doc(null))).toBe('');
		expect(monthOf('-created_at', doc('2026-09-30', '2026-10-01T09:00:00'))).toBe('2026-10');
		// Half past one at night here, the day before in UTC: the month the date shows.
		expect(monthOf('-created_at', doc('2026-09-30', '2026-09-30T23:30:00Z'))).toBe('2026-10');
		expect(monthOf('title', doc('2026-09-30'))).toBeNull();
		expect(monthOf('relevance', doc('2026-09-30'))).toBeNull();
	});

	it('keeps the order, a group for each run of one month', () => {
		const items = [doc('2026-10-14'), doc('2026-10-01'), doc('2026-09-30'), doc(null)];
		const groups = byMonth(items, '-document_date', (item) => item);
		expect(groups.map((group) => [group.month, group.start, group.items.length])).toEqual([
			['2026-10', 0, 2],
			['2026-09', 2, 1],
			['', 3, 1]
		]);
		expect(byMonth(items, 'title', (item) => item)).toEqual([{ month: null, start: 0, items }]);
	});
});
