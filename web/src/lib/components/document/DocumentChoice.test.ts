import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi, json } from '#lib/testing/api.ts';
import DocumentChoice from './DocumentChoice.svelte';

const listed = (id: string, title: string, changes: Record<string, unknown> = {}) => ({
	id,
	title,
	original_filename: `${title}.pdf`,
	media_type: 'application/pdf',
	access: 'edit',
	processing: { status: 'completed' },
	page_count: 2,
	created_at: '2026-11-10T22:41:00Z',
	...changes
});

describe('DocumentChoice', () => {
	it('offers the newest documents, those that cannot join disabled with why', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/documents': () => ({
					items: [
						listed('doc-1', 'Grundsteuerbescheid 2026'),
						listed('doc-2', 'scan_0412'),
						listed('doc-3', 'Rechnung', { media_type: 'message/rfc822' })
					],
					next_cursor: null
				})
			})
		);
		const onpick = vi.fn();
		render(DocumentChoice, { open: true, there: ['doc-1'], onpick });
		const user = userEvent.setup();
		const there = await screen.findByRole('radio', { name: /Grundsteuerbescheid 2026/ });
		expect(there).toHaveProperty('disabled', true);
		expect(there.closest('label')?.textContent).toContain(m.pick_blocked_in());
		const mail = screen.getByRole('radio', { name: /Rechnung/ });
		expect(mail.closest('label')?.textContent).toContain(m.pick_blocked_mail());
		await user.click(screen.getByRole('radio', { name: /scan_0412/ }));
		await user.click(screen.getByRole('button', { name: m.pick_document_add() }));
		expect(onpick).toHaveBeenCalledWith(expect.objectContaining({ id: 'doc-2' }));
	});

	it('does not add a choice the search took out of the list (WA-07)', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/documents': () => ({
					items: [listed('doc-1', 'Grundsteuerbescheid 2026'), listed('doc-2', 'scan_0412')],
					next_cursor: null
				}),
				// The search does not answer: the newest ones are filtered by their title.
				'POST /api/v1/documents/search': () =>
					json({ type: 'about:blank', title: 'Service Unavailable', status: 503 }, 503)
			})
		);
		const onpick = vi.fn();
		render(DocumentChoice, { open: true, there: [], onpick });
		const user = userEvent.setup();
		await user.click(await screen.findByRole('radio', { name: /scan_0412/ }));
		const add = screen.getByRole('button', { name: m.pick_document_add() });
		expect(add).toHaveProperty('disabled', false);
		await user.type(screen.getByRole('searchbox'), 'Grundsteuer');
		await waitFor(() => expect(screen.queryByRole('radio', { name: /scan_0412/ })).toBeNull());
		// It stood chosen and is not shown: before, the button closed the dialog without pages.
		expect(add).toHaveProperty('disabled', true);
		expect(onpick).not.toHaveBeenCalled();
		await user.clear(screen.getByRole('searchbox'));
		await waitFor(() => expect(add).toHaveProperty('disabled', false));
	});
});
