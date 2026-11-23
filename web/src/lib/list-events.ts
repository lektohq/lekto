/**
 * What an event of a document means for a list of documents (the documents list, the inbox).
 * Events are thin, so a list reads itself anew; but most events of a document being processed
 * are about a node of its graph (`NODE_EVENTS`: started, completed, deferred, delegated). They
 * change how far that document is, not which documents a list holds or how many there are:
 * only a list that shows the document reads its rows again, and no count, facet or lens number
 * is asked for. Every other event (received, updated, filed, lane changed, deleted) may change
 * what the list holds and counts.
 */
import { NODE_EVENTS, type DocumentEvent } from '#lib/events.svelte.ts';

/** `none`: the list stays; `rows`: its rows are read again; `all`: its numbers too. */
export type ListRefresh = 'none' | 'rows' | 'all';

export function listRefresh(
	event: Pick<DocumentEvent, 'type' | 'document_id'>,
	shown: (documentId: string) => boolean
): ListRefresh {
	if (!NODE_EVENTS.has(event.type)) return 'all';
	return shown(event.document_id) ? 'rows' : 'none';
}
