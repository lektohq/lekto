import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import SpaceDialog from './SpaceDialog.svelte';

describe('SpaceDialog', () => {
	it('fills its fields when it opens, not again while one types (WC-K02)', async () => {
		const user = userEvent.setup();
		const props = { open: true, title: 'Space', initialName: 'Haushalt', onsubmit: vi.fn() };
		const shown = render(SpaceDialog, props);
		const name = (await screen.findByLabelText(m.field_name())) as HTMLInputElement;
		expect(name.value).toBe('Haushalt');
		await user.clear(name);
		await user.type(name, 'Familie');
		await shown.rerender({ ...props, initialName: 'Haushalt neu' });
		expect(name.value).toBe('Familie');
		await shown.rerender({ ...props, initialName: 'Haushalt neu', open: false });
		await shown.rerender({ ...props, initialName: 'Haushalt neu', open: true });
		expect(((await screen.findByLabelText(m.field_name())) as HTMLInputElement).value).toBe(
			'Haushalt neu'
		);
	});
});
