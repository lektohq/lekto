import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ConnectionTest, Mailbox } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import MailboxDialog from './MailboxDialog.svelte';

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();
const sent: { method: string; path: string; body: unknown }[] = [];
/** The routes that fail for a test, by path. */
const failing = new Set<string>();

function json(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

const STORED: Mailbox = {
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

const FOUND: ConnectionTest = {
	ok: true,
	folders: ['INBOX', 'Archiv'],
	keywords: [],
	own_keywords: true,
	error: null
};

beforeEach(() => {
	session.start({
		user: { id: 'anna', username: 'anna', role: 'admin' },
		method: 'password',
		expires_at: '2026-11-06T12:00:00Z',
		csrf_token: 'token'
	});
	sent.length = 0;
	failing.clear();
	fetchMock.mockReset();
	fetchMock.mockImplementation(async (request) => {
		const path = new URL(request.url).pathname;
		const body = request.method === 'GET' ? null : await request.json().catch(() => null);
		sent.push({ method: request.method, path, body });
		if (failing.has(path)) return json({ detail: 'down' }, 500);
		if (path === '/api/v1/users')
			return json([{ id: 'anna', username: 'anna', display_name: 'Anna', active: true }]);
		if (path === '/api/v1/document-types') return json([]);
		if (path === '/api/v1/mailboxes/test') return json(FOUND);
		if (request.method === 'POST' && path === '/api/v1/mailboxes') return json(STORED, 201);
		return json(STORED);
	});
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
	session.clear();
	vi.unstubAllGlobals();
	// bits-ui frees the page a moment after a dialog closed; the next test must not wait for it.
	window.document.body.style.pointerEvents = '';
});

const testButton = () => screen.getByRole('button', { name: m.mail_test() }) as HTMLButtonElement;

async function fillConnection(user: ReturnType<typeof userEvent.setup>) {
	await user.type(screen.getByLabelText(m.field_name()), 'Haushalt');
	await user.type(screen.getByLabelText(m.mail_host()), 'imap.example.test');
	await user.type(screen.getByLabelText(m.mail_username()), 'haushalt@example.test');
}

describe('MailboxDialog', () => {
	it('tests a new mailbox once it knows where and as whom, then goes on to the folders', async () => {
		const user = userEvent.setup();
		render(MailboxDialog, { open: true, mailbox: null, onsaved: vi.fn() });
		expect(await screen.findByLabelText(m.mail_host())).toBeTruthy();
		await fillConnection(user);
		expect(testButton().disabled).toBe(true); // a new mailbox needs its password
		await user.type(screen.getByLabelText(m.mail_password()), 'secret');
		expect(testButton().disabled).toBe(false);
		await user.click(testButton());
		expect(await screen.findByText(m.mail_test_ok({ count: 2 }))).toBeTruthy();
		const test = sent.find((call) => call.path === '/api/v1/mailboxes/test');
		expect(test?.body).toEqual({
			host: 'imap.example.test',
			port: 993,
			security: 'tls',
			username: 'haushalt@example.test',
			password: 'secret'
		});
		// On to "Abruf", where the folders found are offered next to the inbox chosen already.
		expect(
			screen.getByRole('button', { name: m.mailbox_part_fetch(), pressed: true })
		).toBeTruthy();
		expect(screen.getByRole('checkbox', { name: 'Archiv' })).toBeTruthy();
		expect(screen.getByRole('checkbox', { name: m.mail_folder_inbox() })).toBeTruthy();
	});

	it('creates the mailbox from the form', async () => {
		const user = userEvent.setup();
		const onsaved = vi.fn();
		render(MailboxDialog, { open: true, mailbox: null, onsaved });
		expect(await screen.findByLabelText(m.mail_host())).toBeTruthy();
		const create = screen.getByRole('button', { name: m.create() }) as HTMLButtonElement;
		await fillConnection(user);
		expect(create.disabled).toBe(true); // the password is still missing
		await user.type(screen.getByLabelText(m.mail_password()), 'secret');
		expect(create.disabled).toBe(false);
		await user.click(create);
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalled());
		expect(sent.find((call) => call.path === '/api/v1/mailboxes')).toEqual({
			method: 'POST',
			path: '/api/v1/mailboxes',
			body: {
				name: 'Haushalt',
				host: 'imap.example.test',
				port: 993,
				security: 'tls',
				username: 'haushalt@example.test',
				password: 'secret',
				folders: ['INBOX'],
				interval_minutes: 5,
				start: 'since_setup',
				since: null,
				fallback: 'nothing',
				fallback_user_id: null,
				body_type_id: null
			}
		});
	});

	it('tests and changes a stored mailbox without its password, which stays', async () => {
		const user = userEvent.setup();
		const onsaved = vi.fn();
		render(MailboxDialog, { open: true, mailbox: STORED, onsaved });
		expect(await screen.findByLabelText(m.mail_host())).toBeTruthy();
		expect(testButton().disabled).toBe(false);
		await user.click(testButton());
		expect(await screen.findByText(m.mail_test_ok({ count: 2 }))).toBeTruthy();
		expect(sent.find((call) => call.path === '/api/v1/mailboxes/test')?.body).toEqual({
			host: 'imap.example.test',
			port: 993,
			security: 'tls',
			username: 'haushalt@example.test',
			mailbox_id: 'm1'
		});
		// A stored mailbox stays on the connection after its test.
		expect(
			screen.getByRole('button', { name: m.mailbox_part_connection(), pressed: true })
		).toBeTruthy();
		await user.clear(screen.getByLabelText(m.field_name()));
		await user.type(screen.getByLabelText(m.field_name()), 'Zuhause');
		await user.click(screen.getByRole('button', { name: m.save() }));
		await vi.waitFor(() => expect(onsaved).toHaveBeenCalled());
		const patch = sent.find((call) => call.method === 'PATCH');
		expect(patch?.path).toBe('/api/v1/mailboxes/m1');
		expect(patch?.body).toEqual({
			name: 'Zuhause',
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
			body_type_id: null
		});
	});

	it('shows in "Abruf" when the people and types cannot be loaded, with a retry', async () => {
		const user = userEvent.setup();
		failing.add('/api/v1/users');
		render(MailboxDialog, { open: true, mailbox: STORED, onsaved: vi.fn() });
		const problem = await screen.findByRole('alert');
		expect(problem.textContent).toContain(m.retry());
		failing.clear();
		await user.click(screen.getByRole('button', { name: m.retry() }));
		await vi.waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
		expect(sent.filter((call) => call.path === '/api/v1/users')).toHaveLength(2);
	});
});
