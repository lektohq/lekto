/**
 * What the pages of one rule share (the view, the editor, the apply page, a version), of a
 * document rule and a mail rule alike: the rule's data is loaded beside the master data
 * (`loadRuleLookup` with the webhooks, or the mail rules' `loadMailRuleLookup`), which is kept
 * while the page moves to another rule, and an answer that arrives after a later load started is
 * dropped (another rule in the URL meanwhile, or a reload after a master data dialog saved).
 */
import { untrack } from 'svelte';
import { describeLoad } from '#lib/errors.ts';
import { latest } from '#lib/latest.ts';
import { loadRuleLookup, type Lookup } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';

export class RuleLoader<L = Lookup> {
	/** The master data; null until the first load succeeded. */
	lookup = $state<L | null>(null);
	/** Why the last load failed, as text; null after a load that worked. */
	problem = $state<string | null>(null);
	/** Whether trying again cannot help: the rule is not there, or not the caller's. */
	final = $state(false);
	#begin = latest();
	#last: (() => Promise<void>) | null = null;
	#loadLookup: () => Promise<L>;
	#missing: () => string;

	/** `loadLookup`: the master data the rule's kind needs; a document rule's without.
	 * `missing`: what the page says when its address names nothing (a document rule's without). */
	constructor(loadLookup?: () => Promise<L>, missing: () => string = m.rule_not_found) {
		this.#loadLookup = loadLookup ?? (loadRuleLookup as unknown as () => Promise<L>);
		this.#missing = missing;
	}

	/** "Try again" for `LoadProblem`: none where it cannot help. */
	get onretry(): (() => void) | undefined {
		return this.final ? undefined : () => this.retry();
	}

	/** What was loaded is not the caller's to use here: `text` says why, without a retry. */
	refuse(text: string): void {
		this.problem = text;
		this.final = true;
	}

	/**
	 * Load `data` beside the master data and hand both to `then`, unless a later load overtook
	 * this one; a failure sets `problem`. The master data of the load before is kept unless
	 * `fresh` asks for it anew (a master data dialog saved: the names shown may have changed).
	 */
	async load<T>(
		data: () => Promise<T>,
		then: (found: T, lookup: L) => void,
		options: { fresh?: boolean } = {}
	): Promise<void> {
		this.#last = () => this.load(data, then, options);
		const current = this.#begin();
		const kept = options.fresh ? null : untrack(() => this.lookup);
		try {
			const [found, loaded] = await Promise.all([data(), kept ?? this.#loadLookup()]);
			if (!current()) return;
			this.lookup = loaded;
			this.problem = null;
			this.final = false;
			then(found, loaded);
		} catch (error) {
			if (!current()) return;
			const failure = describeLoad(error, this.#missing);
			this.problem = failure.text;
			this.final = failure.final;
		}
	}

	/** Load again what the last load asked for, after it failed. */
	retry(): void {
		void this.#last?.();
	}
}
