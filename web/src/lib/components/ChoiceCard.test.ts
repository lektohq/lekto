import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import ChoiceCard from './ChoiceCard.svelte';

const words = createRawSnippet(() => ({ render: () => '<span>Every type</span>' }));

describe('ChoiceCard', () => {
	it('is the label of its radio: a click anywhere chooses it', async () => {
		const onchange = vi.fn();
		render(ChoiceCard, { name: 'scope', checked: false, onchange, children: words });
		const radio = screen.getByRole('radio', { name: 'Every type' });
		await userEvent.click(screen.getByText('Every type'));
		expect(onchange).toHaveBeenCalledOnce();
		expect(radio.closest('label')!.className).toContain('has-[>input:checked]:border-primary');
	});

	it('cannot be chosen when disabled', async () => {
		const onchange = vi.fn();
		render(ChoiceCard, { name: 'scope', disabled: true, onchange, children: words });
		await userEvent.click(screen.getByText('Every type'));
		expect(onchange).not.toHaveBeenCalled();
		expect(screen.getByRole('radio')).toHaveProperty('disabled', true);
	});
});
