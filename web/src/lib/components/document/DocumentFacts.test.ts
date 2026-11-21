import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { calls, fakeApi } from '#lib/testing/api.ts';
import DocumentFacts from './DocumentFacts.svelte';

vi.mock('$app/navigation', () => import('#lib/testing/app-navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

describe('DocumentFacts', () => {
	it('shows origin and relations of a document without text (WA-03)', async () => {
		// Neither hangs on the text; a document whose OCR failed never gets one.
		const api = fakeApi({
			'GET /api/v1/documents/d1/relations': () => ({
				refers_to: [],
				referred_by: [
					{
						document: {
							id: 'd2',
							title: 'Mahnung',
							document_type_id: null,
							contact_id: null,
							document_date: null
						},
						origin: 'person',
						state: 'set',
						evidence: {},
						created_at: '2026-11-20T10:00:00Z',
						decided_at: '2026-11-20T10:00:00Z',
						changeable: true
					}
				],
				suggested: [],
				editable: true
			}),
			'GET /api/v1/documents/d1/origin': () => ({ mail: null })
		});
		vi.stubGlobal('fetch', api);
		render(DocumentFacts, {
			facts: null,
			documentId: 'd1',
			mail: true,
			onmark: vi.fn(),
			onshowcode: vi.fn(),
			onchanged: vi.fn()
		});
		expect(screen.getByText(m.facts_pending())).toBeTruthy();
		expect(await screen.findByText('Mahnung')).toBeTruthy();
		expect(screen.getByRole('heading', { name: m.relations_title() })).toBeTruthy();
		expect(calls(api)).toContain('GET /api/v1/documents/d1/origin');
	});
});
