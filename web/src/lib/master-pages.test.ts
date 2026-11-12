import { afterEach, describe, expect, it } from 'vitest';
import { masterSortOf, pageHref, pageOf, rememberMasterSort, sortItems } from './master-pages.ts';

afterEach(() => localStorage.clear());

describe('the sort of a master data list', () => {
	it('is by name until one is chosen; the link wins over the one remembered', () => {
		const none = new URLSearchParams();
		expect(masterSortOf(none, 'contacts')).toBe('name');
		rememberMasterSort('contacts', 'documents');
		expect(masterSortOf(none, 'contacts')).toBe('documents');
		expect(masterSortOf(none, 'document-types')).toBe('name');
		expect(masterSortOf(new URLSearchParams('sort=name'), 'contacts')).toBe('name');
		expect(masterSortOf(new URLSearchParams('sort=nonsense'), 'contacts')).toBe('documents');
	});

	it('forgets "by name" rather than storing it', () => {
		rememberMasterSort('document-types', 'documents');
		rememberMasterSort('document-types', 'name');
		expect(localStorage.getItem('lekto.master-sort.document-types')).toBeNull();
	});

	it('keeps the API’s order by name, or puts the most documents first and keeps it for ties', () => {
		const items = [
			{ id: 'a', document_count: 2 },
			{ id: 'b', document_count: 9 },
			{ id: 'c', document_count: null },
			{ id: 'd', document_count: 9 }
		];
		expect(sortItems(items, 'name').map((item) => item.id)).toEqual(['a', 'b', 'c', 'd']);
		expect(sortItems(items, 'documents').map((item) => item.id)).toEqual(['b', 'd', 'a', 'c']);
	});
});

describe('the page of a master data list', () => {
	it('is the one the link names, else the first', () => {
		expect(pageOf(new URLSearchParams('page=3'))).toBe(3);
		expect(pageOf(new URLSearchParams())).toBe(1);
		expect(pageOf(new URLSearchParams('page=0'))).toBe(1);
		expect(pageOf(new URLSearchParams('page=x'))).toBe(1);
	});

	it('links to a page with the other choices kept, the first without a number', () => {
		const url = new URL('http://lekto/ui/admin/master-data?tab=contacts&sort=documents&page=2');
		expect(pageHref(url, 3)).toBe('?tab=contacts&sort=documents&page=3');
		expect(pageHref(url, 1)).toBe('?tab=contacts&sort=documents');
		expect(pageHref(new URL('http://lekto/ui/admin/master-data?page=2'), 1)).toBe(
			'/ui/admin/master-data'
		);
	});
});
