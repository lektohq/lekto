import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';
import Chip from './Chip.svelte';

const name = createRawSnippet(() => ({ render: () => '<span>12 Monate</span>' }));

describe('a chip that toggles', () => {
	it('shows on by its look alone, at the width of its bolder name', () => {
		render(Chip, { pressed: true, children: name });
		const chip = screen.getByRole('button', { name: '12 Monate', pressed: true });
		// No check: the chips beside it stay where they are.
		expect(chip.querySelector('svg')).toBeNull();
		// The room of the bolder name, from its text.
		expect(chip.querySelector('.steady-weight')?.getAttribute('data-text')).toBe('12 Monate');
	});

	it('keeps the same parts when off', () => {
		render(Chip, { pressed: false, children: name });
		const chip = screen.getByRole('button', { name: '12 Monate', pressed: false });
		expect(chip.querySelector('svg')).toBeNull();
		expect(chip.querySelector('.steady-weight')?.getAttribute('data-text')).toBe('12 Monate');
	});

	it('is a link in the look of a toggle, the current one chosen', () => {
		const { getByRole } = render(Chip, {
			href: '/ui/documents?lens=1',
			current: true,
			children: name
		});
		const link = getByRole('link');
		expect(link.getAttribute('href')).toBe('/ui/documents?lens=1');
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.className).toContain('bg-panel');
	});
});

describe('a chip that is removed (WB-09)', () => {
	it('lets a finger hit its ✕ on a phone: 44 px, over the end of the name too', () => {
		render(Chip, { children: name, onremove: () => {}, removeLabel: 'Filter entfernen' });
		// 24 px drawn, 10 px beyond it above, below and on the right, on a phone on the left too.
		const classes = screen.getByRole('button', { name: 'Filter entfernen' }).className.split(' ');
		expect(classes).toEqual(
			expect.arrayContaining([
				'size-6',
				'after:-inset-y-2.5',
				'after:-right-2.5',
				'max-sm:after:-left-2.5'
			])
		);
	});
});
