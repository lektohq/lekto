import { describe, expect, it } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { ADMIN_RIGHTS, AREAS, grouped, isAdminRight } from '#lib/token-rights.ts';

type Right = components['schemas']['TokenRight'];

describe('token rights', () => {
	it('name every right of the API once', () => {
		const shown = [
			...AREAS.flatMap(({ rights }) => rights.map(([right]) => right)),
			...ADMIN_RIGHTS
		];
		const every: Record<Right, true> = {
			'documents:count': true,
			'documents:read': true,
			'documents:write': true,
			'documents:upload': true,
			'master_data:read': true,
			'master_data:write': true,
			'rules:read': true,
			'rules:write': true,
			'spaces:read': true,
			'spaces:write': true,
			'webhooks:read': true,
			'webhooks:write': true,
			'lenses:read': true,
			'lenses:write': true,
			'push:read': true,
			'push:write': true,
			'system:read': true,
			'system:write': true,
			'admin:count_all': true,
			'admin:documents_all': true,
			'admin:mailboxes': true,
			'admin:private_webhooks': true,
			'admin:manage': true
		};
		expect([...shown].sort()).toEqual(Object.keys(every).sort());
		expect(new Set(shown).size).toBe(shown.length);
	});

	it('group a token by area and keep the admin rights apart', () => {
		expect(
			grouped(['webhooks:write', 'documents:read', 'admin:count_all', 'documents:upload'])
		).toEqual({
			areas: [
				{ area: 'documents', verbs: ['read', 'upload'] },
				{ area: 'webhooks', verbs: ['write'] }
			],
			admin: ['admin:count_all']
		});
		expect(isAdminRight('admin:manage')).toBe(true);
		expect(isAdminRight('system:write')).toBe(false);
	});
});
