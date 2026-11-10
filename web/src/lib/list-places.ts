/**
 * The documents of the list a document was opened from, in its order (web/DESIGN.md,
 * "Navigation between list and detail"): its filters, sort and the documents a link selected
 * come from the list's URL, its words from the way back (`return-to.svelte.ts`). The document
 * view shows where the document stands among them, with the ones before and after it, as it
 * does for the inbox.
 */
import { api } from '#lib/api/client.ts';
import { unwrap } from '#lib/api/call.ts';
import { apiQuery, parseFilters } from '#lib/filters.ts';
import { sortFieldOf, sortOf, type FieldSort, type ListSort, type Sort } from '#lib/listing.ts';
import { selectionOf } from '#lib/selection.ts';

/** The list is read in pages of the most `GET /documents` takes (`tests/api-limits.test.ts`). */
export const LIST_PAGE_MAX = 200;
/** How far previous/next looks into the list, as into the inbox (`INBOX_PLACES_MAX`). */
export const LIST_PLACES_MAX = 1000;
/** A search is read in pages of the most `POST /documents/search` takes. */
export const SEARCH_PAGE_MAX = 100;
/** How far previous/next looks into the hits of a search: each page is a search of its own,
 * so fewer than in a list; a hit further back is opened from the list. */
export const SEARCH_PLACES_MAX = 200;

/** The ids of the list at `url` (its path and query), searched for `words`, in its order. */
export async function listPlaces(url: string, words: string, allUsers: boolean): Promise<string[]> {
	const params = new URL(url, 'http://lekto').searchParams;
	const searching = words.trim() !== '';
	const base = apiQuery(parseFilters(params), allUsers);
	const sort = sortOf(params, searching);
	const ids: string[] = [];
	if (searching) {
		for (let offset = 0; offset < SEARCH_PLACES_MAX; offset += SEARCH_PAGE_MAX) {
			const data = await unwrap(
				api.POST('/api/v1/documents/search', {
					params: {
						query: {
							...base,
							// A search never sorts by a field (`sortOf`).
							sort: sort as Exclude<Sort, FieldSort>,
							offset,
							limit: SEARCH_PAGE_MAX
						}
					},
					body: { q: words }
				})
			);
			ids.push(...data.items.map((hit) => hit.document.id));
			if (data.items.length < SEARCH_PAGE_MAX) break;
		}
		return ids;
	}
	const selected = selectionOf(params);
	const query = selected.length > 0 ? { ...base, ids: selected } : base;
	let cursor: string | null = null;
	do {
		const page: Awaited<ReturnType<typeof listPage>> = await listPage(
			query,
			sort as ListSort,
			sortFieldOf(params, false),
			cursor
		);
		ids.push(...page.items.map((document) => document.id));
		cursor = page.next_cursor;
	} while (cursor !== null && ids.length < LIST_PLACES_MAX);
	return ids;
}

function listPage(
	query: ReturnType<typeof apiQuery> & { ids?: string[] },
	sort: ListSort,
	sortField: string | null,
	cursor: string | null
) {
	return unwrap(
		api.GET('/api/v1/documents', {
			params: {
				query: {
					...query,
					sort,
					sort_field_id: sortField ?? undefined,
					limit: LIST_PAGE_MAX,
					cursor: cursor ?? undefined
				}
			}
		})
	);
}
