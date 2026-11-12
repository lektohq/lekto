/**
 * The pages and the sort of a master data list (Tobi, 12.11.2026). The lists load whole, so the
 * search, a group's filter and the sort go over every item; a page shows 25 of them, or as
 * chosen (`page-size.ts`), and stands in the link (`?page=`), as the documents list's. The
 * contacts and the types sort by name (the API's order) or by most documents, chosen beside the
 * search (`?sort=documents`) and remembered per list in this browser; the fields keep their order
 * (web/DESIGN.md, "Master data tabs").
 */
import { m } from '#lib/paraglide/messages.js';

export const MASTER_SORTS = ['name', 'documents'] as const;
export type MasterSort = (typeof MASTER_SORTS)[number];

/** The lists that offer a sort. */
export type SortedList = 'contacts' | 'document-types';

function isSort(value: string | null): value is MasterSort {
	return (MASTER_SORTS as readonly (string | null)[]).includes(value);
}

function key(list: SortedList): string {
	return `lekto.master-sort.${list}`;
}

/** The sort of `list`: from the URL, else remembered, else by name. */
export function masterSortOf(params: Pick<URLSearchParams, 'get'>, list: SortedList): MasterSort {
	const asked = params.get('sort');
	if (isSort(asked)) return asked;
	let found: string | null = null;
	try {
		found = globalThis.localStorage?.getItem(key(list)) ?? null;
	} catch {
		// Not readable: by name.
	}
	return isSort(found) ? found : 'name';
}

/** Remember `sort` for `list`; by name is forgotten rather than stored. */
export function rememberMasterSort(list: SortedList, sort: MasterSort): void {
	try {
		if (sort === 'name') globalThis.localStorage?.removeItem(key(list));
		else globalThis.localStorage?.setItem(key(list), sort);
	} catch {
		// Not remembered: by name next time.
	}
}

/** The sorts a list offers, for `SortMenu`. */
export function masterSorts(): { value: MasterSort; label: string }[] {
	return [
		{ value: 'name', label: m.master_sort_name() },
		{ value: 'documents', label: m.master_sort_documents() }
	];
}

/** The face of the sort menu: by what, and which way. */
export function masterSortShort(sort: MasterSort): { key: string; direction: 'up' | 'down' } {
	return sort === 'name'
		? { key: m.master_sort_short_name(), direction: 'up' }
		: { key: m.master_sort_short_documents(), direction: 'down' };
}

/** `items` in the order of `sort`: as the API lists them (by name), or the most documents first
 * and those with as many by name. */
export function sortItems<T extends { document_count?: number | null }>(
	items: readonly T[],
	sort: MasterSort
): T[] {
	if (sort === 'name') return [...items];
	return [...items].sort((a, b) => (b.document_count ?? 0) - (a.document_count ?? 0));
}

/** The page the link asks for, from 1. */
export function pageOf(params: Pick<URLSearchParams, 'get'>): number {
	return Math.max(1, Math.floor(Number(params.get('page'))) || 1);
}

/** The link to `page` of the list at `url`, its other choices kept; the first page has none. */
export function pageHref(url: Pick<URL, 'search' | 'pathname'>, page: number): string {
	const params = new URLSearchParams(url.search);
	if (page > 1) params.set('page', String(page));
	else params.delete('page');
	return params.size > 0 ? `?${params}` : url.pathname;
}
