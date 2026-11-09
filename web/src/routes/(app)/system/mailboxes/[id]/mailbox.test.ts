// The page of a mailbox: the tip of its log names how many mails Lekto keeps, as the API says.
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mailbox } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi } from '#lib/testing/documents.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

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
		last_attempt_at: null,
		last_success_at: null,
		error: null,
		mails: 0,
		documents: 0,
		skipped_at: null,
		skipped: null,
		step_failed_at: null,
		step_failed: null,
		keywords: [],
		own_keywords: null
	},
	created_at: '2026-11-04T10:00:00Z',
	updated_at: '2026-11-04T10:00:00Z'
};

const tip = () => screen.queryByRole('button', { name: m.hint_about({ name: m.mailbox_log() }) });

describe('the page of a mailbox', () => {
	beforeEach(() => {
		session.start({
			user: { id: 'u1', username: 'tobi', role: 'admin' },
			method: 'password',
			expires_at: '2026-11-08T12:00:00Z',
			csrf_token: 'token'
		} as never);
		goTo('/ui/system/mailboxes/m1', { id: 'm1' });
	});

	afterEach(() => {
		session.clear();
		vi.unstubAllGlobals();
		localStorage.clear();
	});

	it('names in the log’s tip as many kept mails as the API', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/mailboxes/m1': () => MAILBOX,
				'GET /api/v1/mailboxes/m1/mails': () => ({ items: [], total: 0, next_offset: null }),
				'GET /api/v1/mailboxes/m1/mails/summary': () => ({
					counts: {},
					rules: [],
					waiting: [],
					kept: 300
				})
			})
		);
		render(Page);
		const button = await screen.findByRole('button', {
			name: m.hint_about({ name: m.mailbox_log() })
		});
		await userEvent.setup().click(button);
		expect(await screen.findByText(m.mailbox_log_info({ kept: '300' }))).toBeTruthy();
	});

	it('has no tip while the summary is not there', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/mailboxes/m1': () => MAILBOX,
				'GET /api/v1/mailboxes/m1/mails': () => ({ items: [], total: 0, next_offset: null }),
				'GET /api/v1/mailboxes/m1/mails/summary': () => new Promise(() => {})
			})
		);
		render(Page);
		expect(await screen.findByText(m.mailbox_log())).toBeTruthy();
		expect(tip()).toBeNull();
	});
});
