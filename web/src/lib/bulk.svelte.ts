/**
 * An action on many documents as the page follows it (`POST /documents/bulk`, then its state
 * every second until it is done or failed). The page owns the run, not the bar that shows it:
 * the bar is rendered anew when the window crosses the phone width, and a poll must not go on
 * after the page is left. `stop()` ends the following; a poll in flight changes nothing after it.
 */
import { toast } from 'svelte-sonner';
import { api } from '#lib/api/client.ts';
import { unwrap } from '#lib/api/call.ts';
import type { components } from '#lib/api/schema.ts';
import type { apiQuery } from '#lib/filters.ts';
import { bulkResult } from '#lib/bulk.ts';
import { isPassing, reportError } from '#lib/errors.ts';
import { formatNumber } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';

export type BulkOperation = components['schemas']['BulkOperationOut'];
export type BulkAction = components['schemas']['BulkActionIn'];

/** The documents an action is for: `ids` one by one, else every hit of `query` (the filters)
 * and, with them, `words` (the search; they go in the body, never in an address). */
export interface BulkSelection {
	ids: string[] | null;
	query: Partial<ReturnType<typeof apiQuery>>;
	words?: string;
}

/** How long between two polls of a running operation. */
export const POLL = 1000;

export class BulkRun {
	/** The operation while it runs; null between actions. */
	operation = $state<BulkOperation | null>(null);
	/** The finished operation whose skipped documents are shown ("Details"). */
	skipped = $state<BulkOperation | null>(null);
	/** The last action that skipped documents, until the next one starts: the bar keeps its
	 * "Details", since the toast that offers them is gone after a few seconds. */
	last = $state<BulkOperation | null>(null);
	#stopped = false;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#ondone: () => void;

	/** `ondone` hears of an action that ended: the list loads again. */
	constructor(ondone: () => void) {
		this.#ondone = ondone;
	}

	/** An action runs: the bar stays, with how far it has come, until it ends. */
	get busy(): boolean {
		return this.operation !== null;
	}

	/** Start `action` on `selection` and follow it until it ends. Throws what the API refused. */
	async start(selection: BulkSelection, action: BulkAction): Promise<void> {
		const { ids, query, words } = selection;
		const operation = await unwrap(
			api.POST('/api/v1/documents/bulk', {
				params: { query: ids ? {} : query },
				body: { document_ids: ids, ...(ids || !words ? {} : { q: words }), action }
			})
		);
		if (this.#stopped) return;
		this.last = null;
		this.operation = operation;
		this.#follow(operation.id);
	}

	/** Stop following: no poll changes the state after this (the page is left). */
	stop(): void {
		this.#stopped = true;
		clearTimeout(this.#timer);
	}

	#follow(id: string): void {
		this.#timer = setTimeout(async () => {
			if (this.#stopped) return;
			try {
				const operation = await unwrap(
					api.GET('/api/v1/documents/bulk/{id}', { params: { path: { id } } })
				);
				if (this.#stopped) return;
				this.operation = operation;
				if (operation.status === 'done' || operation.status === 'failed') {
					this.#finish(operation);
					return;
				}
			} catch (error) {
				// A hiccup of the connection or the server restarting: ask again. What the API
				// refuses (the operation is gone, the session another's) it refuses every time:
				// say so and end, the list shows what became of the documents.
				if (!isPassing(error)) {
					if (this.#stopped) return;
					this.operation = null;
					reportError(error);
					this.#ondone();
					return;
				}
			}
			if (!this.#stopped) this.#follow(id);
		}, POLL);
	}

	#finish(operation: BulkOperation): void {
		this.operation = null;
		this.last = operation.skipped.length > 0 ? operation : null;
		const result = bulkResult(operation);
		if (operation.status === 'failed') {
			toast.error(m.bulk_failed(), { description: result });
		} else if (operation.skipped.length > 0) {
			toast.warning(result, {
				description: m.bulk_skipped({ count: formatNumber(operation.skipped.length) }),
				action: { label: m.bulk_details(), onClick: () => (this.skipped = operation) }
			});
		} else {
			toast.success(result);
		}
		this.#ondone();
	}
}
