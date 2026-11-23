import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { newAction, newCondition, newModel } from '#lib/rules/model.ts';
import RuleBuilder from './RuleBuilder.svelte';
import { fieldOf, lookupOf } from '#lib/testing/master-data.ts';

const lookup = lookupOf({
	contacts: [],
	documentTypes: [],
	tags: [],
	fields: [],
	spaces: [],
	users: []
});

const condition = (number: number) => m.rule_row_condition({ number });
const button = (name: string) => screen.getByRole('button', { name });
const focused = () => document.activeElement?.getAttribute('aria-label');

function builder() {
	const model = $state(newModel());
	model.name = 'Regel';
	model.conditions.items = [
		newCondition('contact'),
		newCondition('document_type'),
		newCondition('text')
	];
	model.actions = [newAction('remove_tags')];
	render(RuleBuilder, {
		model,
		lookup,
		targets: [],
		errors: {},
		general: null,
		busy: false,
		cancelHref: '/rules',
		onsubmit: vi.fn()
	});
	return model;
}

describe('the rows of a rule by keyboard (WD-06)', () => {
	it('names each button by its row', () => {
		builder();
		for (const number of [1, 2, 3]) {
			expect(button(m.rule_remove_of({ name: condition(number) }))).toBeTruthy();
		}
		const kind = m.rule_action_remove_tags();
		expect(button(m.rule_remove_of({ name: m.rule_row_action({ number: 1, kind }) }))).toBeTruthy();
	});

	it('draws groups and rows as cards of one size (WD-16)', () => {
		builder();
		const row = button(m.rule_remove_of({ name: condition(1) })).closest('[data-rule-row]')!;
		const classes = row.className.split(' ');
		// `Card` in `sm`, on the page's ground; before: `rounded-xl p-3` by hand.
		expect(classes).toEqual(expect.arrayContaining(['rounded-2xl', 'p-3.5', 'bg-background']));
		expect(classes).not.toContain('rounded-xl');
	});

	it('keeps the focus in the list when a row is removed', async () => {
		const model = builder();
		const user = userEvent.setup();
		const [, second, third] = model.conditions.items;
		button(m.rule_remove_of({ name: condition(2) })).focus();
		await user.keyboard('{Enter}');
		expect(model.conditions.items).not.toContain(second);
		// The row that followed stands in its place, and has the focus.
		expect(focused()).toBe(m.rule_remove_of({ name: condition(2) }));
		expect(document.activeElement?.closest('[data-key]')?.getAttribute('data-key')).toBe(third.key);
		// The last one of its list: the one before it.
		await user.keyboard('{Enter}');
		expect(focused()).toBe(m.rule_remove_of({ name: condition(1) }));
		// The only one: what adds a condition.
		await user.keyboard('{Enter}');
		expect(document.activeElement?.textContent).toContain(m.rule_add_condition());
	});

	it('keeps the focus with a row that moves, on the other way where this one ends', async () => {
		const model = builder();
		const user = userEvent.setup();
		const [first] = model.conditions.items;
		button(m.rule_move_down_of({ name: condition(1) })).focus();
		await user.keyboard('{Enter}');
		expect(model.conditions.items[1]).toBe(first);
		expect(focused()).toBe(m.rule_move_down_of({ name: condition(2) }));
		// On to the last place: there "down" ends, the focus goes to "up" of the same row.
		await user.keyboard('{Enter}');
		expect(model.conditions.items[2]).toBe(first);
		expect(focused()).toBe(m.rule_move_up_of({ name: condition(3) }));
	});

	it('goes to what adds an action when the only action is removed', async () => {
		builder();
		const user = userEvent.setup();
		const kind = m.rule_action_remove_tags();
		button(m.rule_remove_of({ name: m.rule_row_action({ number: 1, kind }) })).focus();
		await user.keyboard('{Enter}');
		expect(document.activeElement?.textContent).toContain(m.rule_add_action());
	});
});

describe('a period in an action', () => {
	const PERIOD = '0199a6c4-0000-7000-8000-0000000000f3';
	const periods = lookupOf({
		fields: [fieldOf({ id: PERIOD, name: 'Bezugszeitraum', data_type: 'period' })]
	});

	it('does not save while a period is written in a way it cannot read', async () => {
		const onsubmit = vi.fn();
		const model = $state(newModel());
		model.name = 'Lohn';
		model.actions = [
			{
				key: newAction('set_field').key,
				type: 'set_field',
				field_id: PERIOD,
				value: { start: '', end: '' }
			}
		];
		render(RuleBuilder, {
			model,
			lookup: periods,
			targets: [],
			errors: {},
			general: null,
			busy: false,
			cancelHref: '/rules',
			onsubmit
		});
		const save = screen.getByRole('button', { name: m.rule_save() }) as HTMLButtonElement;
		const notation = screen.getByLabelText(
			m.field_period_notation_of({ name: m.rule_condition_value() })
		);
		await fireEvent.input(notation, { target: { value: '2026-1' } });
		await fireEvent.blur(notation);
		expect(screen.getByText(m.field_period_unreadable())).toBeTruthy();
		expect(save.disabled).toBe(true);
		await fireEvent.submit(save.form as HTMLFormElement);
		expect(onsubmit).not.toHaveBeenCalled();

		await fireEvent.input(notation, { target: { value: '2026-11' } });
		await fireEvent.blur(notation);
		expect(save.disabled).toBe(false);
		await fireEvent.submit(save.form as HTMLFormElement);
		expect(onsubmit).toHaveBeenCalledOnce();
		expect(model.actions[0]).toMatchObject({ value: { start: '2026-11-01', end: '2026-11-30' } });
	});
});
