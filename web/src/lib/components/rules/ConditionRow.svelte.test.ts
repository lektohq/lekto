import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { Lookup } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { newCondition } from '#lib/rules/model.ts';
import ConditionRow from './ConditionRow.svelte';

const lookup = {
	contacts: [],
	documentTypes: [],
	tags: [],
	fields: [],
	spaces: [],
	users: []
} as unknown as Lookup;

describe('a condition on the mail', () => {
	it('names "Mail" as its subject and the part of the mail in a second choice', () => {
		const condition = $state({ ...newCondition('mail_cc'), value: 'ben@example.test' });
		render(ConditionRow, { condition, lookup, onremove: vi.fn() });
		expect(screen.getByLabelText(m.rule_condition_subject()).textContent).toContain(
			m.rule_field_mail()
		);
		expect(screen.getByLabelText(m.rule_condition_mail_part()).textContent).toContain(
			m.mail_rule_field_cc()
		);
	});

	it('has no second choice for other subjects', () => {
		const condition = $state(newCondition('contact'));
		render(ConditionRow, { condition, lookup, onremove: vi.fn() });
		expect(screen.queryByLabelText(m.rule_condition_mail_part())).toBeNull();
	});
});
