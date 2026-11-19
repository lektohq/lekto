import type { components } from '#lib/api/schema.ts';

/** A right an API token carries (`.knowledge/plans/token-rights.md`). */
export type Right = components['schemas']['TokenRight'];

/** What a right of an area lets do: the word beside its box. */
export type Verb = 'count' | 'read' | 'write' | 'upload';

/** The areas in the order the dialog shows them, each with its rights. */
export const AREAS = [
	{
		area: 'documents',
		rights: [
			['documents:count', 'count'],
			['documents:read', 'read'],
			['documents:write', 'write'],
			['documents:upload', 'upload']
		]
	},
	{
		area: 'master_data',
		rights: [
			['master_data:read', 'read'],
			['master_data:write', 'write']
		]
	},
	{
		area: 'rules',
		rights: [
			['rules:read', 'read'],
			['rules:write', 'write']
		]
	},
	{
		area: 'spaces',
		rights: [
			['spaces:read', 'read'],
			['spaces:write', 'write']
		]
	},
	{
		area: 'webhooks',
		rights: [
			['webhooks:read', 'read'],
			['webhooks:write', 'write']
		]
	},
	{
		area: 'lenses',
		rights: [
			['lenses:read', 'read'],
			['lenses:write', 'write']
		]
	},
	{
		area: 'push',
		rights: [
			['push:read', 'read'],
			['push:write', 'write']
		]
	},
	{
		area: 'system',
		rights: [
			['system:read', 'read'],
			['system:write', 'write']
		]
	}
] as const satisfies readonly { area: string; rights: readonly (readonly [Right, Verb])[] }[];

export type Area = (typeof AREAS)[number]['area'];

/** What an admin may beyond a user, one by one; only for an admin's token. */
export const ADMIN_RIGHTS = [
	'admin:count_all',
	'admin:documents_all',
	'admin:mailboxes',
	'admin:private_webhooks',
	'admin:manage'
] as const satisfies readonly Right[];

export type AdminRight = (typeof ADMIN_RIGHTS)[number];

export function isAdminRight(right: Right): right is AdminRight {
	return (ADMIN_RIGHTS as readonly Right[]).includes(right);
}

/** `rights` by area, in the dialog's order, with the verbs each holds; the admin rights apart. */
export function grouped(rights: readonly Right[]): {
	areas: { area: Area; verbs: Verb[] }[];
	admin: AdminRight[];
} {
	const held = new Set(rights);
	return {
		areas: AREAS.map(({ area, rights: own }) => ({
			area,
			verbs: own.filter(([right]) => held.has(right)).map(([, verb]) => verb)
		})).filter(({ verbs }) => verbs.length > 0),
		admin: ADMIN_RIGHTS.filter((right) => held.has(right))
	};
}
