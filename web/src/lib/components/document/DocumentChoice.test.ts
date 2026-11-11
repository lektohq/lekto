import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
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

afterEach(() => vi.unstubAllGlobals());

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
});
