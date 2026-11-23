/** Builders of master data for tests, in the form the API sends it: what a test does not give
 * is empty, none or false. */
import type {
	Contact,
	DocumentType,
	FieldDefinition,
	Lookup,
	Space,
	Tag,
	UserName
} from '#lib/masterdata.svelte.ts';

/** What a test gives of a thing: its id, and what it is about. */
type Given<T extends { id: string }> = Pick<T, 'id'> & Partial<T>;

const CREATED = '2026-10-01T08:00:00Z';

/** A contact without aliases, identifiers, groups, topics or logo. */
export function contactOf(overrides: Partial<Contact> = {}): Contact {
	return {
		id: 'contact-1',
		name: 'Muster Stadtwerke',
		created_at: CREATED,
		aliases: [],
		identifiers: [],
		group_ids: [],
		topic_ids: [],
		logo: null,
		logo_failure: null,
		...overrides
	};
}

/** A document type without description, title pattern, groups or icon. */
export function documentTypeOf(given: Given<DocumentType>): DocumentType {
	return {
		name: given.id,
		created_at: CREATED,
		description: null,
		title_pattern: null,
		group_ids: [],
		icon: null,
		relation_target: false,
		...given
	};
}

/** A tag of the documents at the top, set by hand and by rules, shown. */
export function tagOf(given: Given<Tag>): Tag {
	const name = given.name ?? given.id;
	return {
		name,
		created_at: CREATED,
		scope: 'document',
		parent_id: null,
		path: [name],
		assignment: 'auto',
		shown: true,
		icon: null,
		color: null,
		...given
	};
}

/** A field of text for every type, not required. */
export function fieldOf(given: Given<FieldDefinition>): FieldDefinition {
	return {
		name: given.id,
		key: given.id,
		data_type: 'text',
		document_type_ids: null,
		choices: [],
		required: false,
		required_document_type_ids: [],
		description: null,
		assignment: 'auto',
		position: 0,
		created_at: CREATED,
		...given
	};
}

/** A shared space the caller edits, without members. */
export function spaceOf(given: Given<Space>): Space {
	return {
		name: given.id,
		personal_of: null,
		description: null,
		role: 'edit',
		members: [],
		created_at: CREATED,
		version: 1,
		...given
	};
}

/** A user by their name. */
export function userOf(given: Given<UserName>): UserName {
	return { username: given.id, ...given };
}

/** The master data of a page; each list empty unless given, each thing as the API sends it. */
export function lookupOf(
	given: {
		contacts?: Partial<Contact>[];
		documentTypes?: Given<DocumentType>[];
		tags?: Given<Tag>[];
		fields?: Given<FieldDefinition>[];
		spaces?: Given<Space>[];
		users?: Given<UserName>[];
	} & Pick<Lookup, 'webhooks' | 'mailboxes'> = {}
): Lookup {
	const { contacts, documentTypes, tags, fields, spaces, users, ...rest } = given;
	return {
		contacts: (contacts ?? []).map(contactOf),
		documentTypes: (documentTypes ?? []).map(documentTypeOf),
		tags: (tags ?? []).map(tagOf),
		fields: (fields ?? []).map(fieldOf),
		spaces: (spaces ?? []).map(spaceOf),
		users: (users ?? []).map(userOf),
		...rest
	};
}
