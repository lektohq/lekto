/**
 * The words of the documents' search live in the history entry (`page.state.words`), never in
 * the address (web/DESIGN.md, "No plain data in addresses"): not in the browser history's
 * addresses, a bookmark or a `Referer`. `persistState` brings them back after a reload. Every
 * navigation of the documents list carries them on; a plain link (none in its state) opens the
 * list without words, or with those of the lens it names.
 *
 * A history entry outlives the session: the next person to sign in in this browser can go back to
 * it. So the entry says whose words it holds (`by`), and they count for that user only.
 */
import { goto } from '$app/navigation';
import { session } from '#lib/session.svelte.ts';

/** The history entry of a search for `words`, of the signed-in user. */
export function wordsState(words: string): App.PageState {
	return { words, by: session.user?.id };
}

/** The words a history entry holds: a string (empty: none) if a navigation of the signed-in
 * user set them, else undefined. */
export function stateWords(state: App.PageState): string | undefined {
	if (typeof state.words !== 'string') return undefined;
	return session.user !== null && state.by === session.user.id ? state.words.trim() : undefined;
}

/** Open `url` searching for `words` (empty: none). */
export function gotoSearching(
	url: string,
	words: string,
	options: { replace?: boolean; reset?: boolean } = {}
): Promise<void> {
	return goto(url, { ...options, state: wordsState(words), persistState: true });
}
