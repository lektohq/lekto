import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { KeptFact } from '#lib/facts.ts';
import { m } from '#lib/paraglide/messages.js';
import FactDecide from './FactDecide.svelte';

const fact: KeptFact = {
	kind: 'invoice_number',
	value: '4711',
	written: '4711',
	role: 'own',
	origins: ['pattern'],
	state: 'found'
};

describe('FactDecide', () => {
	it('keeps what the person typed when the facts load again', async () => {
		const user = userEvent.setup();
		const props = { fact, ondecide: vi.fn(), oncancel: vi.fn() };
		const { rerender } = render(FactDecide, { props });
		const input = screen.getByRole('textbox', { name: m.facts_decide_value() });
		await user.clear(input);
		await user.type(input, '4712');
		await rerender({ ...props, fact: { ...fact } });
		expect((input as HTMLInputElement).value).toBe('4712');
		// Another fact starts anew.
		await rerender({ ...props, fact: { ...fact, value: 'M77', written: 'M-77' } });
		expect((input as HTMLInputElement).value).toBe('M-77');
	});

	it('asks before it removes a fact only a person added (WA-K08)', async () => {
		const user = userEvent.setup();
		const ondecide = vi.fn();
		const added: KeptFact = { ...fact, origins: ['person'], state: 'added' };
		render(FactDecide, { props: { fact: added, ondecide, oncancel: vi.fn() } });
		await user.click(screen.getByRole('button', { name: m.facts_decide_remove() }));
		expect(ondecide).not.toHaveBeenCalled();
		const dialog = await screen.findByRole('alertdialog');
		expect(dialog.textContent).toContain(m.facts_remove_confirm());
		await user.click(within(dialog).getByRole('button', { name: m.facts_decide_remove() }));
		expect(ondecide).toHaveBeenCalledWith({
			kind: 'invoice_number',
			value: '4711',
			action: 'withdraw'
		});
	});
});
