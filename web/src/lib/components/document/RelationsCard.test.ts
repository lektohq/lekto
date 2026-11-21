import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { events } from '#lib/events.svelte.ts';
import { fakeApi, json } from '#lib/testing/api.ts';
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';
import { kindLabel } from '#lib/identifiers.ts';
import { goTo, testPage } from '#lib/testing/page-state.svelte.ts';
import RelationsCard from './RelationsCard.svelte';

vi.mock('$app/navigation', async () => ({
	beforeNavigate: vi.fn(),
	goto: (await import('#lib/testing/page-state.svelte.ts')).fakeGoto
}));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

type Relations = components['schemas']['RelationsOut'];

const other = (id: string, title: string) => ({
	id,
	title,
	document_type_id: null,
	contact_id: null,
	document_date: '2026-06-04'
});

const suggested: Relations = {
	refers_to: [],
	referred_by: [],
	suggested: [
		{
			document: other('invoice', 'Rechnung 4711'),
			origin: 'lekto',
			state: 'suggested',
			evidence: { kind: 'fact', fact_kind: 'invoice_number', value: '4711' },
			created_at: '2026-07-20T10:00:00Z',
			decided_at: null,
			changeable: true
		}
	],
	editable: true
};

const accepted: Relations = {
	...suggested,
	suggested: [],
	refers_to: [{ ...suggested.suggested[0], state: 'set', decided_at: '2026-07-21T10:00:00Z' }]
};

describe('RelationsCard', () => {
	let fetchMock = fakeApi();

	beforeEach(() => {
		fetchMock = fakeApi();
		fetchMock.mockImplementation(async (request) =>
			json(request.method === 'POST' ? accepted : suggested)
		);
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		events.stop();
		vi.unstubAllGlobals();
	});

	/** The event stream of the app; the function sends an event of a document. */
	function stream() {
		const listeners = new Map<string, (message: { data: string }) => void>();
		events.useFactory(
			() =>
				({
					addEventListener(type: string, handler: (message: { data: string }) => void) {
						listeners.set(type, handler);
					},
					close() {}
				}) as unknown as EventSource
		);
		events.start(() => {});
		return (type: string, data: object) =>
			listeners.get(type)?.({
				data: JSON.stringify({ type, id: crypto.randomUUID(), occurred_at: '', ...data })
			});
	}

	it('reads the relations anew when they changed elsewhere (WA-04)', async () => {
		const emit = stream();
		let current = suggested;
		fetchMock.mockImplementation(async () => json(current));
		render(RelationsCard, { props: { documentId: 'reminder', lookup: null } });
		expect(await screen.findByText(m.relations_suggested())).toBeTruthy();
		current = accepted;
		// Another document's relations, and another field of this one: nothing to read.
		emit('document.updated', { document_id: 'other', fields: ['relations'] });
		emit('document.updated', { document_id: 'reminder', fields: ['title'] });
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(fetchMock).toHaveBeenCalledTimes(1);
		emit('document.updated', { document_id: 'reminder', fields: ['relations'] });
		expect(await screen.findByText(m.relations_refers_to())).toBeTruthy();
		expect(screen.queryByText(m.relations_suggested())).toBeNull();
	});

	it('says on the card that it could not load, and tries again (WA-04)', async () => {
		let down = true;
		fetchMock.mockImplementation(async () =>
			down
				? json({ type: 'about:blank', title: 'Error', status: 500, detail: 'boom' }, 500)
				: json(suggested)
		);
		render(RelationsCard, { props: { documentId: 'reminder', lookup: null } });
		expect((await screen.findByRole('alert')).textContent).toContain('boom');
		down = false;
		await userEvent.click(screen.getByRole('button', { name: m.retry() }));
		expect(await screen.findByText('Rechnung 4711')).toBeTruthy();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('shows a suggestion with its evidence and accepts it', async () => {
		const user = userEvent.setup();
		render(RelationsCard, { props: { documentId: 'reminder', lookup: null } });
		expect(await screen.findByText('Rechnung 4711')).toBeTruthy();
		expect(screen.getByText(m.relations_suggested())).toBeTruthy();
		expect(
			screen.getByText(
				m.relations_evidence_fact({ kind: kindLabel('invoice_number'), value: '4711' })
			)
		).toBeTruthy();
		await user.click(
			screen.getByRole('button', { name: m.relations_accept({ title: 'Rechnung 4711' }) })
		);
		await waitFor(() => expect(screen.getByText(m.relations_refers_to())).toBeTruthy());
		const posted = fetchMock.mock.calls.find(([request]) => request.method === 'POST')?.[0];
		expect(new URL(posted!.url).pathname).toBe('/api/v1/documents/reminder/relations');
		expect(await posted!.clone().json()).toEqual({ document_id: 'invoice' });
		expect(screen.queryByText(m.relations_suggested())).toBeNull();
		// The picker is named as it reads, and asks for nothing until it opens.
		expect(screen.getByRole('button', { name: m.relations_add() })).toBeTruthy();
		expect(fetchMock.mock.calls.some(([request]) => request.url.includes('limit=50'))).toBe(false);
	});

	it('offers nothing to change to a reader', async () => {
		const read = { ...accepted.refers_to[0], changeable: false };
		fetchMock.mockImplementation(async () =>
			json({ ...accepted, refers_to: [read], editable: false })
		);
		render(RelationsCard, { props: { documentId: 'reminder', lookup: null } });
		expect(await screen.findByText('Rechnung 4711')).toBeTruthy();
		// Only "Ansehen" (the title), nothing to change.
		expect(
			screen.getAllByRole('button').map((button) => button.getAttribute('aria-label'))
		).toEqual([m.beam_open_named({ title: 'Rechnung 4711' })]);
	});

	it('opens both documents in the Beam, the newer first, the shared number marked', async () => {
		goTo('/ui/documents/reminder');
		const read = { ...accepted.refers_to[0], changeable: false };
		fetchMock.mockImplementation(async (request) =>
			new URL(request.url).pathname === '/api/v1/identifiers/refs'
				? json({ kind: 'invoice_number', value: '4711', ref: 'NDcxMQ' })
				: json({ ...accepted, refers_to: [read], editable: false })
		);
		const user = userEvent.setup();
		render(RelationsCard, {
			props: { documentId: 'reminder', documentTitle: 'Mahnung', lookup: null }
		});
		await user.click(
			await screen.findByRole('button', { name: m.beam_open_named({ title: 'Rechnung 4711' }) })
		);
		await waitFor(() =>
			expect(testPage.state.beam).toEqual({
				ids: ['reminder', 'invoice'],
				index: 1,
				from: 'Mahnung',
				source: { kind: 'fact', identifier: 'invoice_number', ref: 'NDcxMQ' }
			})
		);
	});
});
