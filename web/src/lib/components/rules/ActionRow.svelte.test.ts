// The row of an action, with its model in `$state` as the pages hold it: what the model
// changes, the row shows (WT2-07).
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fakeApi } from '#lib/testing/api.ts';
import { signIn } from '#lib/testing/session.ts';
import type { Lookup } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { newAction, newModel, type ActionNode, type SetFieldNode } from '#lib/rules/model.ts';
import { session } from '#lib/session.svelte.ts';
import ActionRow from './ActionRow.svelte';
import { fieldOf, lookupOf } from '#lib/testing/master-data.ts';

const lookup = lookupOf({
	fields: [
		fieldOf({ id: 'f1', name: 'Netto', key: 'netto', data_type: 'amount' }),
		fieldOf({ id: 'n', name: 'Stunden', key: 'stunden', data_type: 'number' })
	]
});
const targets = [{ value: 'house', label: 'Haushalt' }];

/** The preview of a template, which finds nothing wrong. */
function previews() {
	const api = fakeApi({
		'POST /api/v1/templates/preview': () => ({
			used: [],
			rendered: null,
			missing: null,
			error: null,
			values: null
		})
	});
	vi.stubGlobal('fetch', api);
	return api;
}

/** The row of `action`, held in `$state` as a page holds it. */
function row(action: ActionNode, more: Partial<{ lookup: Lookup }> = {}) {
	const held = $state(action);
	render(ActionRow, { action: held, lookup, targets, onremove: vi.fn(), ...more });
	return held;
}

afterEach(() => {
	session.clear();
});

describe('filing into a space', () => {
	function fileInto(space: string) {
		row({ ...newAction('set_space'), space_id: space } as ActionNode);
	}

	it('keeps a space the caller may not file into and says why saving needs another', () => {
		fileInto('closed');
		expect(screen.getByText(m.rule_space_unreachable_hint())).toBeTruthy();
	});

	it('says nothing about a space the caller files into', () => {
		fileInto('house');
		expect(screen.queryByText(m.rule_space_unreachable_hint())).toBeNull();
	});
});

describe('a template of an action', () => {
	it('names the fields of the rule without asking for them again', async () => {
		const api = previews();
		row(newAction('set_title'));
		await new Promise((resolve) => setTimeout(resolve, 0));
		const asked = api.mock.calls.map(([request]) => new URL(request.url).pathname);
		expect(asked).not.toContain('/api/v1/fields');
	});
});

describe('sending through a webhook', () => {
	function send(webhooks: Lookup['webhooks']) {
		signIn('admin', { id: 'erika', username: 'erika' });
		row(newAction('send_webhook'), { lookup: { ...lookup, webhooks } });
	}

	it('offers only the webhooks of whoever saves the rule', () => {
		send([{ id: 'w1', name: 'Node-RED', owner_id: 'john' }]);
		expect(screen.getByText(m.rule_send_webhook_none())).toBeTruthy();
	});

	it('explains what goes out through an own webhook', () => {
		send([{ id: 'w2', name: 'Home Assistant', owner_id: 'erika' }]);
		expect(screen.getByText(m.rule_send_webhook_hint())).toBeTruthy();
	});
});

describe('steps that ask and check', () => {
	it('asks with a name, a time in minutes and what happens without an answer', () => {
		row(newAction('ask_webhook'));
		expect(screen.getByLabelText(m.rule_ask_name())).toBeTruthy();
		expect((screen.getByLabelText(m.rule_ask_timeout()) as HTMLInputElement).value).toBe('5');
		expect(screen.getByText(m.rule_ask_name_hint())).toBeTruthy();
	});

	it('checks what a step before brought', () => {
		const model = $state(newModel());
		const action = newAction('condition');
		model.actions = [action];
		render(ActionRow, {
			action: model.actions[0],
			lookup,
			targets,
			model,
			steps: ['flow'],
			onremove: vi.fn()
		});
		expect(screen.getByLabelText(m.rule_step_path())).toBeTruthy();
		expect(screen.getByText(m.rule_condition_step_hint())).toBeTruthy();
	});
});

describe('setting a field that is not text', () => {
	function setAmount(value: unknown) {
		previews();
		return row({ ...newAction('set_field'), field_id: 'f1', value } as ActionNode) as SetFieldNode;
	}

	it('switches between a fixed value and a template, carrying the value over', async () => {
		const user = userEvent.setup();
		const action = setAmount({ amount: '12.50', currency: 'EUR' });
		const fixed = screen.getByRole('button', { name: m.rule_value_fixed() });
		expect(fixed.getAttribute('aria-pressed')).toBe('true');
		expect(screen.queryByRole('button', { name: m.template_editor_open() })).toBeNull();

		await user.click(screen.getByRole('button', { name: m.rule_value_template() }));
		// What the person sees follows the model: the template with the value as text.
		expect(action).toMatchObject({ value: '12.50 EUR', templated: true });
		expect(
			screen.getByRole('button', { name: m.rule_value_template() }).getAttribute('aria-pressed')
		).toBe('true');
		expect(screen.getByRole('button', { name: m.template_editor_open() })).toBeTruthy();
		expect(screen.getByDisplayValue('12.50 EUR')).toBeTruthy();

		await user.click(screen.getByRole('button', { name: m.rule_value_fixed() }));
		expect(action).toMatchObject({ value: { amount: '12.50', currency: 'EUR' }, templated: false });
		expect(screen.queryByRole('button', { name: m.template_editor_open() })).toBeNull();
	});

	it('opens a value given as text as a template', () => {
		setAmount('{{ steps.erp.total }} EUR');
		const template = screen.getByRole('button', { name: m.rule_value_template() });
		expect(template.getAttribute('aria-pressed')).toBe('true');
		expect(screen.getByRole('button', { name: m.template_editor_open() })).toBeTruthy();
	});
});

describe('the switch between a fixed value and a template', () => {
	it('stays where it is while the person types', async () => {
		previews();
		const user = userEvent.setup();
		const action = row({
			...newAction('set_field'),
			field_id: 'n',
			value: '12.5'
		} as ActionNode) as SetFieldNode;
		const fixed = screen.getByRole('button', { name: m.rule_value_fixed() });
		expect(fixed.getAttribute('aria-pressed')).toBe('true');

		// Emptied or half typed, a number is no template: the input stays.
		const input = screen.getByLabelText(m.rule_condition_value());
		await user.clear(input);
		await user.type(input, '-');
		expect(
			screen.getByRole('button', { name: m.rule_value_fixed() }).getAttribute('aria-pressed')
		).toBe('true');
		expect(action.templated).toBe(false);
	});

	it('starts a new action with a fixed value', () => {
		row({ ...newAction('set_field'), field_id: 'n' } as ActionNode);
		const fixed = screen.getByRole('button', { name: m.rule_value_fixed() });
		expect(fixed.getAttribute('aria-pressed')).toBe('true');
	});
});
