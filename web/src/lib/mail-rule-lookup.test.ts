import { describe, expect, it } from 'vitest';
import type { DocumentType, Space, UserName } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { namesOf } from './mail-rule-lookup.ts';

const users = [
	{ id: 'u1', username: 'anna', display_name: 'Anna Busch', active: true }
] as UserName[];
const spaces = [{ id: 's1', name: 'Haushalt' }] as Space[];
const types = [{ id: 't1', name: 'E-Mail' }] as DocumentType[];

describe('the names a mail rule shows', () => {
	it('names a person as a choice names them, spaces and types by name', () => {
		const names = namesOf({ users, spaces, types });
		expect(names.user('u1')).toBe('Anna Busch (anna)');
		expect(names.space('s1')).toBe('Haushalt');
		expect(names.type('t1')).toBe('E-Mail');
	});

	it('says "unknown" for what is gone', () => {
		const names = namesOf({ users, spaces, types });
		expect(names.user('nobody')).toBe(m.rule_unknown());
		expect(names.space(null)).toBe(m.rule_unknown());
		expect(names.type(undefined)).toBe(m.rule_unknown());
	});
});
