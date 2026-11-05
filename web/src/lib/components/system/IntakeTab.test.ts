import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mailbox } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import IntakeTab from './IntakeTab.svelte';

const MAILBOX: Mailbox = {
	id: 'm1',
	name: 'Haushalt',
	host: 'imap.example.test',
	port: 993,
	security: 'tls',
	username: 'haushalt@example.test',
	folders: ['INBOX'],
	interval_minutes: 5,
	start: 'since_setup',
	since: null,
	fallback: 'nothing',
	fallback_user_id: null,
	body_type_id: null,
	enabled: true,
	status: {
		last_attempt_at: '2026-11-05T09:00:00Z',
		last_success_at: '2026-11-05T09:00:00Z',
		error: null,
		mails: 3,
		documents: 4,
		skipped_at: '2026-11-05T09:00:00Z',
		skipped: { code: 'mail_too_large', params: { subject: 'Fotos', size: 180, max: 134 } },
		step_failed_at: null,
		step_failed: null,
		keywords: [],
		own_keywords: null
	},
	created_at: '2026-11-04T10:00:00Z',
	updated_at: '2026-11-04T10:00:00Z'
};

describe('IntakeTab', () => {
	beforeEach(() => {
		vi.stubGlobal(
			'fetch',
			vi.fn(
				async () =>
					new Response(JSON.stringify([MAILBOX]), {
						headers: { 'content-type': 'application/json' }
					})
			)
		);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('shows a mail left out because it was too large', async () => {
		render(IntakeTab);
		expect(await screen.findByText('Haushalt')).toBeTruthy();
		expect(screen.getByText(m.mail_status_ok())).toBeTruthy();
		expect(screen.getByText(/Fotos/)).toBeTruthy();
		expect(screen.getByText(/180/)).toBeTruthy();
	});
});
