/** Builders of master data for tests, in the form the API sends it. */
import type { components } from '#lib/api/schema.ts';

type Contact = components['schemas']['ContactOut'];

/** A contact without aliases, identifiers, groups, topics or logo. */
export function contactOf(overrides: Partial<Contact> = {}): Contact {
	return {
		id: 'contact-1',
		name: 'Muster Stadtwerke',
		created_at: '2026-10-01T08:00:00Z',
		aliases: [],
		identifiers: [],
		group_ids: [],
		topic_ids: [],
		logo: null,
		logo_failure: null,
		...overrides
	};
}
