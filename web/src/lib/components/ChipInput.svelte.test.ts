import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import ChipInput from './ChipInput.svelte';

function field(values: string[], { maxlength = 200, max = 100 } = {}) {
	const props = $state({
		values,
		addLabel: 'Schreibweise',
		inputLabel: 'Neue Schreibweise',
		maxlength,
		max
	});
	render(ChipInput, props);
	return props;
}

describe('ChipInput', () => {
	it('adds with Enter, once in any case, and removes with the cross', async () => {
		const user = userEvent.setup();
		const props = field(['Nord AG']);
		await user.click(screen.getByRole('button', { name: 'Schreibweise' }));
		const input = screen.getByLabelText('Neue Schreibweise');
		expect(document.activeElement).toBe(input);
		await user.type(input, 'Nord KV{Enter}');
		expect(props.values).toEqual(['Nord AG', 'Nord KV']);
		// The input stays for the next one.
		expect((input as HTMLInputElement).value).toBe('');
		await user.type(input, 'nord kv{Enter}');
		expect(props.values).toEqual(['Nord AG', 'Nord KV']);
		await user.click(screen.getByRole('button', { name: m.alias_remove({ name: 'Nord AG' }) }));
		expect(props.values).toEqual(['Nord KV']);
	});

	it('adds what was typed on leaving, each pasted line apart, and leaves on Escape alone', async () => {
		const user = userEvent.setup();
		const props = field([]);
		// The dialog around listens for Escape on the document.
		const outside = vi.fn((event: KeyboardEvent) => event.key);
		document.addEventListener('keydown', outside);
		await user.click(screen.getByRole('button', { name: 'Schreibweise' }));
		const input = screen.getByLabelText('Neue Schreibweise');
		await fireEvent.paste(input, {
			clipboardData: { getData: () => 'Nord Leben AG\nNord KV\n\n' }
		});
		expect(props.values).toEqual(['Nord Leben AG', 'Nord KV']);
		await user.type(input, 'Nord Bank');
		await user.tab();
		expect(props.values).toEqual(['Nord Leben AG', 'Nord KV', 'Nord Bank']);
		await user.click(screen.getByRole('button', { name: 'Schreibweise' }));
		await user.keyboard('{Escape}');
		expect(screen.queryByLabelText('Neue Schreibweise')).toBeNull();
		expect(outside.mock.results.map((result) => result.value)).not.toContain('Escape');
		document.removeEventListener('keydown', outside);
	});

	it('takes values as long and as many as the API does; what does not fit stays typed', async () => {
		const user = userEvent.setup();
		const props = field(['Nord AG'], { maxlength: 10, max: 3 });
		await user.click(screen.getByRole('button', { name: 'Schreibweise' }));
		const input = screen.getByLabelText('Neue Schreibweise') as HTMLInputElement;
		expect(input.maxLength).toBe(10);
		await fireEvent.paste(input, {
			clipboardData: { getData: () => 'Nord Lebensversicherung\nNord KV\nNord Bank\nNord Rente' }
		});
		// Too long, and beyond three: not added, but left in the input to see and shorten.
		expect(props.values).toEqual(['Nord AG', 'Nord KV', 'Nord Bank']);
		// At the limit the field takes no more: no input, no dashed chip.
		expect(screen.queryByLabelText('Neue Schreibweise')).toBeNull();
		expect(screen.queryByRole('button', { name: 'Schreibweise' })).toBeNull();
		await user.click(screen.getByRole('button', { name: m.alias_remove({ name: 'Nord KV' }) }));
		await user.click(screen.getByRole('button', { name: 'Schreibweise' }));
		expect((screen.getByLabelText('Neue Schreibweise') as HTMLInputElement).value).toBe(
			'Nord Lebensversicherung Nord Rente'
		);
	});
});
