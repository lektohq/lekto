/**
 * The log of a mailbox (Tobi, 06.11.2026; mock „Postfach-Seite mit Verarbeitung“): what became
 * of each mail it fetched, in the words of its page. The outcomes of the API come together as the
 * page's views: "Übernommen" holds a mail a rule took with nothing in it to take as well.
 */
import type { components } from '#lib/api/schema.ts';
import { formatDate } from '#lib/i18n.ts';
import { stepText } from '#lib/mail-rules.ts';
import { m } from '#lib/paraglide/messages.js';
import { reasonText } from '#lib/reasons.ts';
import type { Tone } from '#lib/tones.ts';

export type MailItem = components['schemas']['MailOut'];
export type MailOutcome = components['schemas']['MailOutcome'];
export type MailSummary = components['schemas']['MailSummaryOut'];

export const VIEWS = ['all', 'taken', 'no_rule', 'too_large', 'failed', 'known'] as const;
export type MailView = (typeof VIEWS)[number];

export const VIEW_OUTCOMES: Record<MailView, MailOutcome[] | undefined> = {
	all: undefined,
	taken: ['taken', 'nothing'],
	no_rule: ['no_rule'],
	too_large: ['too_large'],
	failed: ['failed'],
	known: ['known']
};

export const VIEW_LABELS: Record<MailView, () => string> = {
	all: m.mailbox_view_all,
	taken: m.mailbox_view_taken,
	no_rule: m.mailbox_view_no_rule,
	too_large: m.mailbox_view_too_large,
	failed: m.mailbox_view_failed,
	known: m.mailbox_view_known
};

/** The view a mail's outcome belongs to, for its badge. */
export function viewOf(outcome: MailOutcome): MailView {
	return outcome === 'nothing' ? 'taken' : outcome;
}

/** Lane colours mean state (web/DESIGN.md "Badges"): taken green, left out yellow, failed red. */
export const VIEW_TONE: Record<Exclude<MailView, 'all'>, Tone> = {
	taken: 'green',
	no_rule: 'muted',
	too_large: 'yellow',
	failed: 'red',
	known: 'muted'
};

/** How many mails of the summary a view shows. */
export function viewCount(summary: MailSummary, view: MailView): number {
	const outcomes = VIEW_OUTCOMES[view];
	return Object.entries(summary.counts).reduce(
		(sum, [outcome, count]) =>
			!outcomes || outcomes.includes(outcome as MailOutcome) ? sum + (count ?? 0) : sum,
		0
	);
}

/** Who took it, under the badge: a rule (afterwards: when), the fallback, nothing in it. */
export function takenText(item: MailItem): string {
	if (item.outcome !== 'taken' && item.outcome !== 'nothing') return '';
	const parts = [item.rule ? m.mailbox_by_rule({ name: item.rule }) : m.mailbox_by_fallback()];
	if (item.outcome === 'nothing') parts.push(m.mailbox_nothing_taken());
	if (item.later && item.decided_at) {
		parts.push(m.mailbox_later({ date: formatDate(item.decided_at, { dateStyle: 'short' }) }));
	}
	return parts.join(' · ');
}

/** A line under the badge that wants attention: the rule that takes a waiting mail at the next
 * fetch, a mail gone from its folder, why it was left out or failed. */
export function noteOf(item: MailItem): string {
	if (item.next_rule) return m.mailbox_next_rule({ name: item.next_rule.name });
	if (item.outcome === 'no_rule' && item.gone_at) return m.mailbox_gone();
	if (item.reason && (item.outcome === 'too_large' || item.outcome === 'failed')) {
		return reasonText(item.reason);
	}
	return '';
}

/** What happened on the server, the steps done; a refused one apart (`failedSteps`). */
export function stepsDone(item: MailItem): string {
	return item.steps
		.filter((step) => !step.failed)
		.map((step) => stepText(step))
		.join(', ');
}

export function failedSteps(item: MailItem): string[] {
	return item.steps.flatMap((step) =>
		step.failed
			? [m.mailbox_step_failed({ step: stepText(step), reason: reasonText(step.failed) })]
			: []
	);
}

/** The note over the log: how many waiting mails which rules take at the next fetch. */
export function waitingText(summary: MailSummary): string {
	const count = summary.waiting.reduce((sum, item) => sum + item.mails, 0);
	if (count === 0) return '';
	const rules = summary.waiting
		.map((item) => m.mailbox_waiting_rule({ name: item.rule.name, count: item.mails }))
		.join(', ');
	return count === 1
		? m.mailbox_waiting_note_one({ rules })
		: m.mailbox_waiting_note({ count, rules });
}
