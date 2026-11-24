import { render, screen, waitFor } from '@testing-library/svelte';
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

describe('TagChip in its colours', () => {
	it('draws a tag in its colour with its icon', async () => {
		const { container } = render(TagChip, {
			tag: { id: 'x', name: 'Health', path: ['Health'], icon: 'heart-pulse', color: 'pink' }
		});
		const chip = container.querySelector('[title="Health"]') as HTMLElement;
		expect(chip.getAttribute('style')).toContain(
			'--chip-bg: var(--tag-pink); --chip-fg: var(--tag-pink-foreground)'
		);
		expect(chip.className).toContain('bg-(--chip-bg)');
		await waitFor(() => expect(chip.querySelector('svg.lucide-heart-pulse')).not.toBeNull());
	});

	it('mixes an own colour so that the writing stays readable in each theme', () => {
		const { container } = render(TagChip, {
			tag: { id: 'x', name: 'Weiß', path: ['Weiß'], color: '#FFFFFF' },
			topic: true
		});
		const chip = container.querySelector('[title="Weiß"]') as HTMLElement;
		expect(chip.className).toContain('chip-own');
		expect(chip.className).toContain('rounded-full');
		const style = chip.getAttribute('style') ?? '';
		expect(style).toContain('--chip-own: #ffffff');
		const light = Number(/--chip-light: (\d+)%/.exec(style)?.[1]);
		expect(light).toBeLessThan(70);
	});

	it('keeps an uncoloured tag as it was', () => {
		const { container } = render(TagChip, { tag: { id: 'x', name: 'Plain', path: ['Plain'] } });
		const chip = container.querySelector('[title="Plain"]') as HTMLElement;
		expect(chip.getAttribute('style')).toBeNull();
		expect(chip.className).toContain('bg-secondary');
	});
});
