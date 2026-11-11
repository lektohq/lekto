/**
 * Merging documents (web/DESIGN.md, "Page stack"; `POST /documents/{id}/edit` with
 * `documents`): which documents can be merged, and why one cannot. The API checks the same:
 * the caller edits every one, none is processed or a mail, and its pages are there to show.
 */
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';

type Listed = components['schemas']['ListedDocument'];

/** What the stack needs of a document to take its pages. */
export type Mergeable = Pick<Listed, 'id' | 'title' | 'page_count'>;

/** What tells whether a document can be merged. */
export type Candidate = Mergeable &
	Pick<Listed, 'media_type' | 'access' | 'processing' | 'original_filename' | 'created_at'>;

/** The most other documents one merge takes (the API's `MAX_MERGED`). */
export const MAX_MERGED = 20;

/** Why `document` cannot join the stack now, or null: on it already (`there`), a mail, being
 * processed, not to be edited by the caller, or without its page images. */
export function mergeBlock(document: Candidate, there: readonly string[] = []): string | null {
	if (there.includes(document.id)) return m.pick_blocked_in();
	if (document.media_type === 'message/rfc822') return m.pick_blocked_mail();
	if (document.processing.status === 'processing') return m.pick_blocked_processing();
	if (document.access !== 'edit') return m.pick_blocked_rights();
	if (!document.page_count) return m.pick_blocked_pages();
	return null;
}

/** Why the chosen documents (in their order, those the page knows) cannot be merged, or null.
 * `count`: how many are chosen; `all`: every hit is, not single ones. */
export function mergeBlocked(
	chosen: readonly Candidate[],
	count: number,
	all: boolean
): string | null {
	if (all) return m.bulk_merge_single();
	if (count < 2) return m.bulk_merge_two();
	if (count > MAX_MERGED + 1) return m.bulk_merge_many({ count: String(MAX_MERGED + 1) });
	for (const document of chosen) {
		const reason = mergeBlock(document);
		if (reason) return m.bulk_merge_blocked({ title: document.title, reason });
	}
	return null;
}
