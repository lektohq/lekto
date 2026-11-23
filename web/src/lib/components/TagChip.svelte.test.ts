import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import TagChip from './TagChip.svelte';

const tag = { id: 't1', name: 'Steuer', path: ['Finanzen', 'Steuer'], color: 'green' };

describe('TagChip as a toggle', () => {
	it('is a pressed button in its colour, ringed when chosen, its path as the title', async () => {
		const onclick = vi.fn();
		const { rerender } = render(TagChip, { tag, pressed: false, size: 'sm', onclick });
		const chip = screen.getByRole('button', { name: 'Steuer' });
		expect(chip.getAttribute('aria-pressed')).toBe('false');
		expect(chip.getAttribute('title')).toBe('Finanzen › Steuer');
		expect(chip.className).toContain('h-6');
		await userEvent.click(chip);
		expect(onclick).toHaveBeenCalledOnce();
		await rerender({ tag, pressed: true, size: 'md', onclick });
		expect(chip.getAttribute('aria-pressed')).toBe('true');
		expect(chip.className).toContain('ring-primary');
		expect(chip.className).toContain('h-8');
	});
});

describe('TagChip that is removed (WB-09)', () => {
	const remove = () => screen.getByRole('button', { name: 'Steuer entfernen' }).className;

	it('lets its ✕ reach over a name that is only text, on a phone', () => {
		render(TagChip, { tag, onremove: () => {}, removeLabel: 'Steuer entfernen' });
		expect(remove()).toContain('max-sm:after:-left-2.5');
	});

	it('keeps the ✕ off a name that is a target itself', () => {
		const props = { tag, onremove: () => {}, removeLabel: 'Steuer entfernen' };
		const picked = render(TagChip, { ...props, onpick: () => {}, pickLabel: 'Steuer ändern' });
		expect(remove()).not.toContain('max-sm:after:-left-2.5');
		picked.unmount();
		render(TagChip, { ...props, interactive: true });
		expect(remove()).not.toContain('max-sm:after:-left-2.5');
	});
});
