import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import MultiPicker from './MultiPicker.svelte';

const options = Array.from({ length: 5 }, (_, n) => ({ value: `f${n}`, label: `Ordner ${n}` }));
const box = (label: string) => screen.getByRole('checkbox', { name: label }) as HTMLInputElement;

describe('MultiPicker', () => {
	it('takes no more than the API does, and says so (WT2-08)', () => {
		// 25 folders found, 20 taken: more would be refused when saving (422).
		const props = {
			options,
			selected: ['f0', 'f1'],
			onchange: vi.fn(),
			label: 'Ordner',
			max: 2,
			full: 'Höchstens 2 Ordner.'
		};
		const { rerender } = render(MultiPicker, props);
		expect(box('Ordner 2').disabled).toBe(true);
		// What is chosen can be taken back.
		expect(box('Ordner 0').disabled).toBe(false);
		expect(screen.getByText('Höchstens 2 Ordner.')).toBeTruthy();

		rerender({ ...props, selected: ['f0'] });
		expect(box('Ordner 2').disabled).toBe(false);
		expect(screen.queryByText('Höchstens 2 Ordner.')).toBeNull();
	});

	it('takes any number without a maximum', () => {
		render(MultiPicker, {
			options,
			selected: options.map((option) => option.value),
			onchange: vi.fn(),
			label: 'Werte'
		});
		expect(
			screen.getAllByRole('checkbox').every((each) => !(each as HTMLInputElement).disabled)
		).toBe(true);
	});
});
