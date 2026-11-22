import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Lookup } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { newAction, newCondition, newModel } from '#lib/rules/model.ts';
import RuleBuilder from './RuleBuilder.svelte';

const lookup = {
	contacts: [],
	documentTypes: [],
	tags: [],
	topics: [],
	fields: [],
	spaces: [],
	users: []
} as unknown as Lookup;

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
