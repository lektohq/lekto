import { describe, expect, it } from 'vitest';
import { describeValue, fieldLabel } from './describe.ts';
import type { Lookup } from './masterdata.svelte.ts';

const lookup = {
	contacts: [{ id: 'c1', name: 'Muster AG', created_at: '' }],
	documentTypes: [],
	tags: [{ id: 't1', name: 'Tax', created_at: '' }],
	fields: [{ id: 'a1', name: 'Due', data_type: 'date' }],
	spaces: [],
	users: [
		{ id: 'u1', username: 'jane', personal_space_id: 's1' },
		{ id: 'u2', username: 'john', personal_space_id: 's2' }
	]
} as unknown as Lookup;

describe('describing changes', () => {
	it('names ids', () => {
		expect(describeValue('c1', lookup)).toBe('Muster AG');
		expect(describeValue(['t1', 'zz'], lookup)).toBe('Tax, zz');
		expect(describeValue({ start: '2026-09-01', end: '2026-09-30' }, lookup)).toBe('2026-09');
		expect(describeValue('u1', lookup)).toBe('jane');
		// The personal space of a user the caller is no member of: by that user.
		expect(describeValue('s2', lookup)).toBe('john');
	});

	it('shows plain values', () => {
		expect(describeValue(true, lookup)).not.toBe('');
		expect(describeValue('hello', lookup)).toBe('hello');
		expect(describeValue({ amount: '1.5', currency: 'EUR' }, lookup)).toContain('1');
	});

	it('names fields', () => {
		expect(fieldLabel('field:a1', lookup)).toBe('Due');
		expect(fieldLabel('field:zz', lookup)).toBe('field:zz');
	});
});
