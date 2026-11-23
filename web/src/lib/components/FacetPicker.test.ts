import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import FacetPicker from './FacetPicker.svelte';

const item = (id: string, label: string) => ({ id, label, count: 1 });

afterEach(() => phone.override(null));

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

	it('forgets its search when closed with "Fertig" (WB-K02)', async () => {
		const user = userEvent.setup();
		const shown = render(FacetPicker, {
			open: true,
			title: 'Kontakte',
			searchLabel: 'Kontakte durchsuchen',
			items: [item('c1', 'Apotheke Muster'), item('c2', 'Bäckerei Muster')],
			selected: [],
			onchange: vi.fn()
		});
		const dialog = await screen.findByRole('dialog', { name: 'Kontakte' });
		await user.type(within(dialog).getByLabelText('Kontakte durchsuchen'), 'Bäck');
		await user.click(within(dialog).getByRole('button', { name: m.facet_done() }));
		await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
		await shown.rerender({ open: true });
		const again = await screen.findByRole('dialog', { name: 'Kontakte' });
		expect((within(again).getByLabelText('Kontakte durchsuchen') as HTMLInputElement).value).toBe(
			''
		);
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

	it('is a sheet from the bottom on a phone, with rows a finger tall and no field in focus (WB-12)', async () => {
		phone.override(true);
		const onchange = vi.fn();
		render(FacetPicker, {
			open: true,
			title: 'Kontakte',
			searchLabel: 'Kontakte durchsuchen',
			items: [item('c1', 'Apotheke Muster'), item('c2', 'Bäckerei Muster')],
			selected: [],
			onchange
		});
		const sheet = await screen.findByRole('dialog', { name: 'Kontakte' });
		expect(sheet.getAttribute('data-side')).toBe('bottom');
		// The keyboard waits for a tap: the search does not take the focus.
		expect(document.activeElement).not.toBe(within(sheet).getByRole('searchbox'));
		const row = within(sheet).getAllByRole('checkbox')[0].closest('label')!;
		expect(row.className.split(' ')).toContain('max-sm:min-h-12');
		// The way out stands in the head of the sheet.
		expect(within(sheet).getByRole('button', { name: m.facet_done() })).toBeTruthy();
	});
});
