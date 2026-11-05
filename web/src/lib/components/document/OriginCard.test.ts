import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';
import OriginCard from './OriginCard.svelte';

type Origin = components['schemas']['OriginOut'];

const attachment: Origin = {
	mail: {
		mailbox: 'Haushalt',
		rule: null,
		role: 'attachment',
		filename: 'Rechnung 4711.pdf',
		subject: 'Ihre Rechnung',
		sender: [{ name: 'Stadtwerke', address: 'rechnung@stadtwerke.example' }],
		to: [{ name: '', address: 'anna@example.test' }],
		cc: [{ name: '', address: 'carl@example.test' }],
		sent_at: '2026-11-04T09:00:00Z',
		arrived_at: '2026-11-04T09:01:00Z',
		forwarded_by: [{ name: 'Ben', address: 'ben@example.test' }],
		message_id: 'r-4711@stadtwerke.example',
		importance: 'high',
		keywords: ['Lekto', '$label1'],
		flag: 'green'
	}
};

describe('OriginCard', () => {
	const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
	let answer: Origin = attachment;

	beforeEach(() => {
		fetchMock.mockReset();
		fetchMock.mockImplementation(
			async () =>
				new Response(JSON.stringify(answer), { headers: { 'content-type': 'application/json' } })
		);
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('names the mail a document came with', async () => {
		answer = attachment;
		render(OriginCard, { props: { documentId: 'd1' } });
		expect(await screen.findByText('Haushalt')).toBeTruthy();
		expect(screen.getByText(m.origin_title())).toBeTruthy();
		expect(screen.getByText(m.origin_fallback())).toBeTruthy();
		expect(screen.getByText('Stadtwerke <rechnung@stadtwerke.example>')).toBeTruthy();
		expect(screen.getByText('anna@example.test')).toBeTruthy();
		expect(screen.getByText('Ben <ben@example.test>')).toBeTruthy();
		expect(screen.getByText('Rechnung 4711.pdf')).toBeTruthy();
		expect(screen.queryByText(m.origin_forwarded())).toBeTruthy();
		expect(screen.getByText('carl@example.test')).toBeTruthy();
		expect(screen.getByText(m.mail_importance_high())).toBeTruthy();
		expect(screen.getByText('Lekto, $label1')).toBeTruthy();
		expect(screen.getByText(m.mail_flag_green())).toBeTruthy();
		const [request] = fetchMock.mock.calls[0];
		expect(new URL(request.url).pathname).toBe('/api/v1/documents/d1/origin');
	});

	it('leaves out what the mail had not or Lekto did not know', async () => {
		answer = {
			mail: { ...attachment.mail!, importance: 'normal', keywords: null, flag: null, cc: [] }
		};
		render(OriginCard, { props: { documentId: 'd3' } });
		expect(await screen.findByText('Haushalt')).toBeTruthy();
		for (const label of [
			m.origin_importance(),
			m.origin_keywords(),
			m.origin_flag(),
			m.origin_cc()
		]) {
			expect(screen.queryByText(label)).toBeNull();
		}
	});

	it('shows nothing for a document no mail brought', async () => {
		answer = { mail: null };
		render(OriginCard, { props: { documentId: 'd2' } });
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
		await vi.waitFor(() => expect(screen.queryByText(m.origin_title())).toBeNull());
	});

	it('keeps a load error on the card, with a way to try again', async () => {
		fetchMock.mockImplementation(async () => new Response('down', { status: 503 }));
		render(OriginCard, { props: { documentId: 'd4' } });
		expect(await screen.findByRole('alert')).toBeTruthy();
		expect(screen.getByText(m.origin_title())).toBeTruthy();
	});
});
