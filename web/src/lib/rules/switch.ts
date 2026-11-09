import { toast } from 'svelte-sonner';
import { api } from '#lib/api/client.ts';
import { unwrap } from '#lib/api/call.ts';
import type { components } from '#lib/api/schema.ts';
import { reportError } from '#lib/errors.ts';
import type { MailRule } from '#lib/mail-rules.ts';
import type { Mailbox } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';

type Rule = components['schemas']['RuleOut'];

// Switching a rule or a mailbox on and off, the one way (web/DESIGN.md, "Mail rules": one set of
// parts and words for every rule): the change, a toast that says what happened, an error as
// every error. The caller keeps what comes back (null: it failed and was reported) and shows
// itself busy meanwhile.

async function switched<T>(change: () => Promise<T>, said: string): Promise<T | null> {
	try {
		const result = await change();
		toast.success(said);
		return result;
	} catch (error) {
		reportError(error);
		return null;
	}
}

/** A document rule on or off. */
export function switchRule(id: string, enabled: boolean): Promise<Rule | null> {
	return switched(
		() => unwrap(api.PATCH('/api/v1/rules/{id}', { params: { path: { id } }, body: { enabled } })),
		enabled ? m.rule_switched_on() : m.rule_switched_off()
	);
}

/** A mail rule on or off; `said` in place of the usual toast (the dry run says what it takes). */
export function switchMailRule(
	id: string,
	enabled: boolean,
	said?: string
): Promise<MailRule | null> {
	return switched(
		() =>
			unwrap(api.PATCH('/api/v1/mail-rules/{id}', { params: { path: { id } }, body: { enabled } })),
		said ?? (enabled ? m.rule_switched_on() : m.rule_switched_off())
	);
}

/** A mailbox on or off. */
export function switchMailbox(id: string, enabled: boolean): Promise<Mailbox | null> {
	return switched(
		() =>
			unwrap(api.PATCH('/api/v1/mailboxes/{id}', { params: { path: { id } }, body: { enabled } })),
		enabled ? m.mailbox_switched_on() : m.mailbox_switched_off()
	);
}
