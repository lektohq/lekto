import { unwrap } from '#lib/api/call.ts';
import { api } from '#lib/api/client.ts';
import type { components } from '#lib/api/schema.ts';

type Hit = components['schemas']['SearchResultItem']['document'];

/** How long a picker waits after a key before it asks. */
export const TYPING_PAUSE_MS = 250;

/**
 * The documents a picker shows for what was typed: the words of all documents (no meaning, at
 * most 20), and where the search does not answer, those of the newest ones whose title holds
 * the text. For an effect that reads the text: it returns the effect's cleanup. What was found
 * before stays until the answer is there, so the list does not fall back to the newest ones at
 * every key; without a text nothing is found (`null`: show the newest).
 */
export function searchTyped<T extends { title: string }>(
	typed: string,
	to: {
		/** The newest documents, to fall back on. */
		recent: () => readonly T[];
		/** What the picker keeps of a hit. */
		read: (document: Hit) => T;
		show: (found: T[] | null) => void;
	}
): (() => void) | undefined {
	const text = typed.trim();
	if (!text) {
		to.show(null);
		return undefined;
	}
	let current = true;
	const timer = setTimeout(() => {
		void unwrap(
			api.POST('/api/v1/documents/search', {
				params: { query: { limit: 20, semantic_ratio: 0 } },
				body: { q: text }
			})
		).then(
			(page) => {
				if (current) to.show(page.items.map((item) => to.read(item.document)));
			},
			() => {
				const wanted = text.toLocaleLowerCase();
				if (current) {
					to.show(to.recent().filter((item) => item.title.toLocaleLowerCase().includes(wanted)));
				}
			}
		);
	}, TYPING_PAUSE_MS);
	return () => {
		current = false;
		clearTimeout(timer);
	};
}
