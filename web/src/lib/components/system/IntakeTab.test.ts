import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeApi } from '#lib/testing/api.ts';
import { m } from '#lib/paraglide/messages.js';
import IntakeTab from './IntakeTab.svelte';
import { mailboxOf } from '#lib/testing/system.ts';

const MAILBOX = mailboxOf({
	status: {
		last_attempt_at: '2026-11-05T09:00:00Z',
		last_success_at: '2026-11-05T09:00:00Z',
		mails: 3,
		documents: 4,
		skipped_at: '2026-11-05T09:00:00Z',
		skipped: { code: 'mail_too_large', params: { subject: 'Fotos', size: 180, max: 134 } }
	}
});

describe('IntakeTab', () => {
	beforeEach(() => {
		vi.stubGlobal('fetch', fakeApi({ 'GET /api/v1/mailboxes': () => [MAILBOX] }));
	});

	it('shows a mail left out because it was too large', async () => {
		render(IntakeTab);
		expect(await screen.findByText('Haushalt')).toBeTruthy();
		expect(screen.getByText(m.mail_status_ok())).toBeTruthy();
		expect(screen.getByText(/Fotos/)).toBeTruthy();
		expect(screen.getByText(/180/)).toBeTruthy();
	});
});
