import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import FacetPicker from './FacetPicker.svelte';

const item = (id: string, label: string) => ({ id, label, count: 1 });

describe('FacetPicker', () => {
	it('opens with names that start with an umlaut, under the plain letter', async () => {
		render(FacetPicker, {
			open: true,
			title: 'Kontakte',
			searchLabel: 'Kontakte durchsuchen',
			items: [
				item('c1', 'Apotheke Muster'),
				item('c2', 'Ärztekammer Muster'),
				item('c3', 'Auto Muster'),
				item('c4', 'Bäckerei Muster')
			],
			selected: [],
			onchange: vi.fn()
		});
		const dialog = await screen.findByRole('dialog', { name: 'Kontakte' });
		// One "A" for the three, in the order of the language; it used to come twice and break.
		expect(within(dialog).getAllByText('A')).toHaveLength(1);
		expect(
			within(dialog)
				.getAllByRole('checkbox')
				.map((box) => box.closest('label')?.textContent?.trim().replace(/\s+1$/, ''))
		).toEqual(['Apotheke Muster', 'Ärztekammer Muster', 'Auto Muster', 'Bäckerei Muster']);
	});

	it('shows two values of one name, each to choose', async () => {
		render(FacetPicker, {
			open: true,
			title: 'Kontakte',
			searchLabel: 'Kontakte durchsuchen',
			items: [item('c1', 'Muster Bank'), item('c2', 'Muster Bank')],
			selected: [],
			onchange: vi.fn()
		});
		const dialog = await screen.findByRole('dialog', { name: 'Kontakte' });
		expect(within(dialog).getAllByRole('checkbox')).toHaveLength(2);
	});
});
