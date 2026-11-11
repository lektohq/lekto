/**
 * The documents page's own search field, where the header has a magnifier instead of its own
 * (`header-search.ts`): on the documents page the magnifier brings that field into view and
 * gives it the focus, rather than opening the page anew (which would drop its filters). The
 * page offers how while it is open; elsewhere the magnifier is a link to it (`#search`).
 */

let reveal: (() => void) | null = null;

/** Offer how to show the field; returns what takes the offer back. */
export function offerPageSearch(show: () => void): () => void {
	reveal = show;
	return () => {
		if (reveal === show) reveal = null;
	};
}

/** Show the page's field, if the page offers it; whether it did. */
export function showPageSearch(): boolean {
	if (!reveal) return false;
	reveal();
	return true;
}
