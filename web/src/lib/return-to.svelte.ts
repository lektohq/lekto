/**
 * Where "back" leads from a document (web/DESIGN.md, "Navigation between list and detail"): the
 * document list as it was left, with its lens, filters, sort and layout, which live in its URL,
 * and its words, which live in the history entry (`lib/words.ts`), at the place it was left at
 * (`lib/list-place.svelte.ts`); the inbox at its place too. Kept in memory for this tab; after
 * a reload the way back is the bare list.
 */
import { BASE } from '#lib/base.ts';
import { gotoWithState } from '#lib/held-state.ts';
import type { Place } from '#lib/list-place.svelte.ts';
import { wordsState } from '#lib/words.ts';

let documents = $state<string | null>(null);
let words = $state('');
const places = $state<{ documents: Place | null; inbox: Place | null }>({
	documents: null,
	inbox: null
});

export const returnTo = {
	/** The document list as it was left, or the bare list. */
	get documents(): string {
		return documents ?? `${BASE}/documents`;
	},
	/** The list as it was left, with its words; null before the list was shown in this tab
	 * (after a reload): then a document knows no neighbours there (`lib/list-places.ts`). */
	get list(): { url: string; words: string } | null {
		return documents === null ? null : { url: documents, words };
	},
	/** The history entry of the way back: the words the list searched for, and where one
	 * stood in it. */
	get state(): App.PageState {
		return { ...wordsState(words), ...(places.documents && { place: places.documents }) };
	},
	/** The history entry of the way back to the inbox: where one stood in it. */
	get inboxState(): App.PageState {
		return places.inbox ? { place: places.inbox } : {};
	},
	/** A list remembers where one stands in it when one leaves it. */
	rememberPlace(list: 'documents' | 'inbox', place: Place): void {
		places[list] = place;
	},
	/** The list remembers its URL and words whenever they change. */
	rememberDocuments(url: { pathname: string; search: string }, searched: string): void {
		documents = url.pathname + url.search;
		words = searched;
	},
	/** Back to the list as it was left. */
	goDocuments(): Promise<void> {
		return gotoWithState(documents ?? `${BASE}/documents`, this.state);
	},
	/** Back to the inbox as it was left. */
	goInbox(): Promise<void> {
		return gotoWithState(`${BASE}/inbox`, this.inboxState);
	}
};
