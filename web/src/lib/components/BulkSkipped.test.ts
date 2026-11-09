import { render, screen, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { reasonText, type Reason } from '#lib/reasons.ts';
import { documentOf } from '#lib/testing/documents.ts';
import { calls, fakeApi } from '#lib/testing/api.ts';
import BulkSkipped from './BulkSkipped.svelte';

afterEach(() => vi.unstubAllGlobals());

const reason = (code: Reason['code'], params: Reason['params'] = {}): Reason => ({ code, params });

describe('the skipped documents of an action on many', () => {
	it('names each by title with why, and one no longer readable by its reason alone', async () => {
		const api = fakeApi({
			'GET /api/v1/documents': () => ({
				items: [documentOf({ id: 'd1', title: 'Strom 2026' })],
				next_cursor: null,
				total: 1
			})
		});
		vi.stubGlobal('fetch', api);
		const busy = reason('being_processed', { id: 'd1' });
		const gone = reason('skip_not_available');
		render(BulkSkipped, {
			operation: {
				skipped: [
					{ document_id: 'd1', reason: 'busy', reasons: [busy] },
					{ document_id: 'd2', reason: 'gone', reasons: [gone] }
				]
			},
			onclose: vi.fn()
		});
		const dialog = await screen.findByRole('dialog', { name: m.bulk_details_title() });
		await within(dialog).findByRole('button', { name: m.beam_open_named({ title: 'Strom 2026' }) });
		expect(dialog.textContent).toContain(reasonText(busy));
		expect(dialog.textContent).toContain(m.bulk_unknown_document());
		expect(dialog.textContent).toContain(reasonText(gone));
	});

	it('asks for all titles in one request', async () => {
		const ids = ['d1', 'd2', 'd3', 'd4'];
		const api = fakeApi({
			'GET /api/v1/documents': (_request, url) => ({
				items: url.searchParams
					.getAll('ids')
					.map((id) => documentOf({ id, title: `Dokument ${id}` })),
				next_cursor: null,
				total: ids.length
			})
		});
		vi.stubGlobal('fetch', api);
		render(BulkSkipped, {
			operation: {
				skipped: ids.map((id) => ({ document_id: id, reason: 'busy', reasons: [] }))
			},
			onclose: vi.fn()
		});
		const dialog = await screen.findByRole('dialog', { name: m.bulk_details_title() });
		for (const id of ids)
			await within(dialog).findByRole('button', {
				name: m.beam_open_named({ title: `Dokument ${id}` })
			});
		const asked = calls(api);
		expect(asked).toHaveLength(1);
		expect(asked[0]).toBe('GET /api/v1/documents?ids=d1&ids=d2&ids=d3&ids=d4&limit=50');
	});
});
