/**
 * Applying a rule to existing documents: what the preview selects and what the request holds
 * (decision E3: documents with a conflict are only applied with their own consent, which
 * becomes `accept_conflicts`), how often the progress is asked for, what a queued application
 * waits for and what a finished one did.
 */
import type { components } from '#lib/api/schema.ts';
import { describeValue, fieldLabel } from '#lib/describe.ts';
import { formatNumber } from '#lib/i18n.ts';
import type { JobsSummary } from '#lib/jobs.ts';
import { spaceNameFor, type Lookup } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { labelled, outputReasonText, reasonsText } from '#lib/reasons.ts';

export type PreviewItem = components['schemas']['ApplyPreviewItemOut'];
export type Application = components['schemas']['RuleApplicationOut'];
export type ApplyRequest = components['schemas']['ApplyRequest'];

/** The job kind of rule applications. */
const APPLY_JOB = 'rules.apply';

export function hasConflict(item: PreviewItem): boolean {
	return item.conflicts.length > 0;
}

/** The documents chosen when they show up: those without a conflict. */
export function preselected(items: readonly PreviewItem[]): string[] {
	return items.filter((item) => !hasConflict(item)).map((item) => item.document_id);
}

/** The request for the chosen documents, in the order of the preview. A conflict counts only
 * as accepted; a chosen document with a conflict that is not accepted stays out. */
export function applyRequest(
	version: number,
	items: readonly PreviewItem[],
	chosen: ReadonlySet<string>,
	accepted: ReadonlySet<string>
): ApplyRequest {
	const included = items.filter((item) =>
		hasConflict(item) ? accepted.has(item.document_id) : chosen.has(item.document_id)
	);
	return {
		version,
		document_ids: included.map((item) => item.document_id),
		accept_conflicts: included.filter(hasConflict).map((item) => item.document_id)
	};
}

export type Effect = components['schemas']['RuleEffectOut'];

/** What a rule changes on every document of a group alike: the field and its new value, the old
 * one where it is the same on all of them (else undefined). */
export interface SharedEffect {
	field: string;
	old?: unknown;
	new: unknown;
}

/** Documents of a dry run the rule changes in the same fields (and, with a conflict, in the
 * same conflicting fields): one card, its changes said once in the head. */
export interface PreviewGroup {
	key: string;
	conflict: boolean;
	items: PreviewItem[];
	shared: SharedEffect[];
	/** The conflicts, where they read the same on every document. */
	conflicts: PreviewItem['conflicts'];
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The dry run's documents by what the rule changes on them, in the order the first of each
 * came; those with a conflict last. */
export function groupPreview(items: readonly PreviewItem[]): PreviewGroup[] {
	const groups = new Map<string, PreviewItem[]>();
	for (const item of items) {
		const names = (list: readonly { field: string }[]) => list.map((entry) => entry.field);
		const key = JSON.stringify([names(item.changes).toSorted(), names(item.conflicts).toSorted()]);
		const members = groups.get(key);
		if (members) members.push(item);
		else groups.set(key, [item]);
	}
	const found = [...groups].map(([key, members]): PreviewGroup => {
		const [first, ...rest] = members;
		return {
			key,
			conflict: hasConflict(first),
			items: members,
			shared: sharedEffects(first, rest),
			conflicts: rest.every((item) => same(item.conflicts, first.conflicts)) ? first.conflicts : []
		};
	});
	return [...found.filter((group) => !group.conflict), ...found.filter((group) => group.conflict)];
}

function sharedEffects(first: PreviewItem, rest: readonly PreviewItem[]): SharedEffect[] {
	const of = (item: PreviewItem, field: string) =>
		item.changes.find((effect) => effect.field === field);
	return first.changes
		.filter((effect) => rest.every((item) => same(of(item, effect.field)?.new, effect.new)))
		.map((effect) =>
			rest.every((item) => same(of(item, effect.field)?.old, effect.old))
				? { field: effect.field, old: effect.old, new: effect.new }
				: { field: effect.field, new: effect.new }
		);
}

/** The changes of `item` its group's head does not say. */
export function ownEffects(item: PreviewItem, group: PreviewGroup): Effect[] {
	return item.changes.filter(
		(effect) => !group.shared.some((shared) => shared.field === effect.field)
	);
}

export function isFinished(application: Pick<Application, 'status'>): boolean {
	return application.status === 'done' || application.status === 'failed';
}

/**
 * The jobs a queued application waits for (`GET /jobs/summary`): the worker runs the pipeline's
 * steps before rule applications (and the index after them), and the applications by when they
 * are due; `own` of the applications is the one waiting.
 */
export function ahead(summary: Pick<JobsSummary, 'kinds'>, own = 1): number {
	let jobs = 0;
	for (const kind of summary.kinds) {
		if (kind.kind.startsWith('pipeline.')) jobs += kind.running + kind.due;
		else if (kind.kind === APPLY_JOB) jobs += Math.max(0, kind.running + kind.due - own);
	}
	return jobs;
}

/** What waits before the application, in words. */
export function aheadText(jobs: number): string {
	if (jobs === 0) return m.rule_apply_next();
	return jobs === 1 ? m.rule_apply_ahead_one() : m.rule_apply_ahead({ count: formatNumber(jobs) });
}

/** What an application did: changed, unchanged, skipped. */
export function applicationResult(application: Application): string {
	return m.rule_apply_result({
		applied: formatNumber(application.applied),
		unchanged: formatNumber(application.unchanged),
		skipped: formatNumber(application.skipped.length)
	});
}

/** Every second at first, then every three. */
export function pollDelay(elapsedMs: number): number {
	return elapsedMs < 10_000 ? 1000 : 3000;
}

/**
 * Ask for the progress until the application is finished or `signal` aborts; `update` gets each
 * answer. Resolves with the last one.
 */
export async function follow(
	first: Application,
	load: (id: string) => Promise<Application>,
	update: (application: Application) => void,
	signal: AbortSignal,
	wait: (ms: number) => Promise<void> = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
): Promise<Application> {
	let current = first;
	let elapsed = 0;
	while (!isFinished(current) && !signal.aborted) {
		const delay = pollDelay(elapsed);
		await wait(delay);
		elapsed += delay;
		if (signal.aborted) break;
		current = await load(current.id);
		update(current);
	}
	return current;
}

export type Outcome = components['schemas']['ApplyOutcomeOut'];

/** The notes of a chain step that tell why it stopped or what did not act. */
const CHAIN_NOTES = new Set(['refused', 'conflict']);

/**
 * Where applying the rule takes a document, step by step: into the space `rule` files it into,
 * then what the rules of each space it enters do ("then tags Haushaltskosten (rule “Rechnungen”
 * of Haushalt)"), where the chain stops and why, and where it ends up.
 */
export function chainLines(
	outcome: Outcome,
	rule: string,
	lookup: Lookup | null,
	me: string | undefined
): string[] {
	const name = (id: string) => spaceNameFor(id, lookup, me);
	const first = outcome.chain[0]?.space_id ?? outcome.space_id;
	const lines = [m.rule_chain_into({ space: name(first), rule })];
	const visited = [first];
	for (const step of outcome.chain) {
		const here = name(step.space_id);
		for (const report of step.rules) {
			for (const effect of report.applied) {
				if (effect.field === 'space') continue; // the move, below
				const change = `${fieldLabel(effect.field, lookup)} ${describeValue(effect.new, lookup)}`;
				lines.push(m.rule_chain_then({ change, rule: report.name, space: here }));
			}
			for (const note of report.notes.filter((entry) => CHAIN_NOTES.has(entry.kind))) {
				const field = fieldLabel(note.field, lookup);
				const reason =
					reasonsText(note.reasons, note.reason, {
						field: (name) => fieldLabel(name, lookup)
					}) ?? note.reason;
				lines.push(m.rule_chain_note({ field, reason, rule: report.name, space: here }));
			}
		}
		if (step.moved_to !== null) {
			const mover = step.rules.find((report) =>
				report.applied.some((effect) => effect.field === 'space')
			);
			lines.push(
				m.rule_chain_moved({ space: name(step.moved_to), rule: mover?.name ?? '', from: here })
			);
			visited.push(step.moved_to);
		}
		if (step.looped_to !== null) {
			const spaces = [...visited, step.looped_to].map(name).join(' → ');
			lines.push(m.rule_chain_loop({ spaces }));
		} else if (step.problem !== null) {
			const problem =
				outputReasonText(step.problem_reason, step.problem, labelled(lookup)) ?? step.problem;
			lines.push(m.rule_chain_problem({ problem }));
		}
	}
	if (outcome.chain.length > 0) lines.push(m.rule_chain_end({ space: name(outcome.space_id) }));
	return lines;
}
