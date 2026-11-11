import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import AssignmentList from './AssignmentList.svelte';

const candidates = [
	{ id: 'invoice', name: 'Rechnung' },
	{ id: 'reminder', name: 'Mahnung', hint: 'field.mahnung' },
	{ id: 'letter', name: 'Brief' }
];

function props(onchange = vi.fn(), assigned = [{ id: 'invoice', required: true }]) {
	return {
		assigned,
		candidates,
		label: 'Typen',
		addLabel: 'Typ hinzufügen',
		emptyLabel: 'Keine',
		onchange
	};
}

// The popover is placed by measuring, which jsdom does not: its options count as hidden and
// have no accessible name there, so they are found by their text.
const option = async (name: string) =>
	(await screen.findByText(name, { selector: '[role="option"] span' })).closest('[role="option"]')!;

afterEach(() => phone.override(null));

describe('AssignmentList', () => {
	it('adds from a sheet on a phone, named by what it adds', async () => {
		phone.override(true);
		const onchange = vi.fn();
		render(AssignmentList, props(onchange));
		await userEvent.click(screen.getByRole('button', { name: 'Typ hinzufügen' }));
		const sheet = await screen.findByRole('dialog', { name: 'Typ hinzufügen' });
		await userEvent.click(within(sheet).getByRole('option', { name: /Brief/ }));
		expect(onchange).toHaveBeenLastCalledWith([
			{ id: 'invoice', required: true },
			{ id: 'letter', required: false }
		]);
		await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
	});

	it('shows the assigned ones with required and remove, and adds from a search', async () => {
		const onchange = vi.fn();
		render(AssignmentList, props(onchange));
		const required = screen.getByRole('switch', {
			name: m.assignment_required_for({ name: 'Rechnung' })
		});
		expect(required.getAttribute('aria-checked')).toBe('true');
		await userEvent.click(screen.getByRole('button', { name: 'Typ hinzufügen' }));
		// Only those not assigned yet; the search narrows them.
		expect(screen.queryByText('Rechnung', { selector: '[role="option"] span' })).toBeNull();
		await userEvent.type(screen.getByRole('combobox', { hidden: true }), 'mah');
		expect(screen.queryByText('Brief', { selector: '[role="option"] span' })).toBeNull();
		await userEvent.click(await option('Mahnung'));
		expect(onchange).toHaveBeenLastCalledWith([
			{ id: 'invoice', required: true },
			{ id: 'reminder', required: false }
		]);
	});

	it('makes one optional or removes it', async () => {
		const onchange = vi.fn();
		render(AssignmentList, props(onchange));
		await userEvent.click(
			screen.getByRole('switch', { name: m.assignment_required_for({ name: 'Rechnung' }) })
		);
		expect(onchange).toHaveBeenLastCalledWith([{ id: 'invoice', required: false }]);
		await userEvent.click(
			screen.getByRole('button', { name: m.assignment_remove({ name: 'Rechnung' }) })
		);
		expect(onchange).toHaveBeenLastCalledWith([]);
	});

	it('says when none is assigned', () => {
		render(AssignmentList, props(vi.fn(), []));
		expect(screen.getByText('Keine')).toBeTruthy();
	});
});
