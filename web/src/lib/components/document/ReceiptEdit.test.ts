import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
import ReceiptEdit from './ReceiptEdit.svelte';

describe('setting when a document came in', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('takes day and time in the date field of the UI and saves them', async () => {
		let body: unknown = null;
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'PATCH /api/v1/documents/doc-1': async (request) => {
					body = await request.json();
					return {};
				}
			})
		);
		const onchanged = vi.fn();
		render(ReceiptEdit, { documentId: 'doc-1', value: '2026-10-26T12:00:00Z', onchanged });
		await fireEvent.click(screen.getByRole('button', { name: m.files_received_edit() }));
		await screen.findByRole('dialog');
		const field = screen
			.getAllByLabelText(m.files_received_label())
			.find((element) => element.tagName === 'INPUT') as HTMLInputElement;
		expect(field.dataset.stand).toBe('DateInput');
		expect(field.type).toBe('datetime-local');
		await fireEvent.input(field, { target: { value: '2026-10-27T09:15' } });
		await fireEvent.click(screen.getByRole('button', { name: m.save() }));
		await vi.waitFor(() => expect(onchanged).toHaveBeenCalled());
		expect(body).toEqual({ created_at: new Date('2026-10-27T09:15').toISOString() });
	});
});
