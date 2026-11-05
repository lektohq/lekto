/**
 * What the pages of a mail rule load besides the rule: the mailboxes, the users, every space
 * (the person of a rule files into one) and the document types; and the names a rule shows.
 */
import { api } from '#lib/api/client.ts';
import { unwrap } from '#lib/api/call.ts';
import type { Names } from '#lib/mail-rules.ts';
import type { Mailbox } from '#lib/mailboxes.ts';
import {
	userChoice,
	type DocumentType,
	type Space,
	type UserName
} from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';

export interface MailRuleLookup {
	mailboxes: Mailbox[];
	users: UserName[];
	spaces: Space[];
	types: DocumentType[];
}

export async function loadMailRuleLookup(): Promise<MailRuleLookup> {
	const [mailboxes, users, spaces, types] = await Promise.all([
		unwrap(api.GET('/api/v1/mailboxes')),
		unwrap(api.GET('/api/v1/users')),
		unwrap(api.GET('/api/v1/spaces', { params: { query: { all_users: true } } })),
		unwrap(api.GET('/api/v1/document-types'))
	]);
	return { mailboxes, users, spaces, types };
}

/** The names a mail rule shows: a person as a choice names them, spaces and types by name. */
export function namesOf(lookup: Pick<MailRuleLookup, 'users' | 'spaces' | 'types'>): Names {
	return {
		user: (id) => {
			const user = lookup.users.find((entry) => entry.id === id);
			return user ? userChoice(user) : m.rule_unknown();
		},
		space: (id) => lookup.spaces.find((entry) => entry.id === id)?.name ?? m.rule_unknown(),
		type: (id) => lookup.types.find((entry) => entry.id === id)?.name ?? m.rule_unknown()
	};
}
