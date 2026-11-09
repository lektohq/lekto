import { Pager } from '#lib/paging.svelte.ts';

/** A page of a log and the summary that comes with it (its counts by outcome, its filters). */
export interface SummaryPage<T, S> {
	items: T[];
	total: number;
	summary: S;
}

/**
 * A log shown page by page with its summary, as on the page of a webhook and of a mailbox
 * (web/DESIGN.md, "Intake channels": the mailbox page is built as the page of a webhook). Each
 * page brings its summary along; the summary of the latest page asked for wins over one that
 * comes late.
 */
export class SummaryPager<T, S> {
	summary = $state<S | null>(null);
	readonly pager: Pager<T>;
	#asked = 0;

	constructor(load: (offset: number, limit: number) => Promise<SummaryPage<T, S>>, size: number) {
		this.pager = new Pager<T>(async (offset, limit) => {
			const ask = ++this.#asked;
			const found = await load(offset, limit);
			if (ask === this.#asked) this.summary = found.summary;
			return found;
		}, size);
	}

	/** Forget the summary and start over from the first page. */
	reset(): Promise<void> {
		this.summary = null;
		return this.pager.reload();
	}
}
