import { fireEvent, render, screen } from '@testing-library/svelte';
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

describe('a condition on a date', () => {
	it('takes the document date in the date field of the UI, not of the browser', async () => {
		const condition = $state({
			...newCondition('document_date'),
			op: 'gt' as const,
			value: '2026-10-26'
		});
		render(ConditionRow, { condition, lookup, onremove: vi.fn() });
		const field = screen.getByLabelText(m.rule_condition_value()) as HTMLInputElement;
		expect(field.dataset.stand).toBe('DateInput');
		expect(field.value).toBe('2026-10-26');
		await fireEvent.input(field, { target: { value: '2026-11-01' } });
		expect(condition.value).toBe('2026-11-01');
	});

	it('compares a step after a date in the date field of the UI', async () => {
		const condition = $state({
			...newCondition('step'),
			path: 'answer.due',
			op: 'gt' as const,
			value: '2026-10-26'
		});
		render(ConditionRow, { condition, lookup, onremove: vi.fn() });
		const field = screen.getByLabelText(m.rule_condition_value()) as HTMLInputElement;
		expect(field.dataset.stand).toBe('DateInput');
		await fireEvent.input(field, { target: { value: '2026-12-24' } });
		expect(condition.value).toBe('2026-12-24');
	});
});
