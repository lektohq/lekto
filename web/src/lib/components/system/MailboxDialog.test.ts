import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LIMITS, type ConnectionTest } from '#lib/mailboxes.ts';
import { signIn } from '#lib/testing/session.ts';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import MailboxDialog from './MailboxDialog.svelte';
import {
	fakeApi,
	json,
	problem,
	recording,
	type Route,
	type Routes,
	type Sent
} from '#lib/testing/api.ts';
import { mailboxOf } from '#lib/testing/system.ts';

let fetchMock: ReturnType<typeof fakeApi>;
const sent: Sent[] = [];
/** The routes that fail for a test, by path. */
const failing = new Set<string>();

const STORED = mailboxOf();

const FOUND: ConnectionTest = {
	ok: true,
	folders: ['INBOX', 'Archiv'],
	keywords: [],
	own_keywords: true,
	error: null
};

beforeEach(() => {
	signIn('admin', { id: 'erika', username: 'erika' });
	sent.length = 0;
	failing.clear();
	// What `failing` names fails; each request is kept in `sent`.
	const or =
		(route: Route): Route =>
		(request, url) =>
			failing.has(url.pathname)
				? problem(500, { detail: 'an unexpected error occurred' })
				: route(request, url);
	const routes: Routes = {
		'GET /api/v1/users': () => [
			{ id: 'erika', username: 'erika', display_name: 'Erika', active: true }
		],
		'GET /api/v1/document-types': () => [],
		'POST /api/v1/mailboxes/test': () => FOUND,
		'POST /api/v1/mailboxes': () => json(STORED, 201),
		[`PATCH /api/v1/mailboxes/${STORED.id}`]: () => STORED
	};
	fetchMock = fakeApi(
		recording(
			Object.fromEntries(Object.entries(routes).map(([key, route]) => [key, or(route)])),
			sent
		)
	);
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
	session.clear();
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
		// In the part "Abruf", where the people and types are chosen: hidden while "Verbindung"
		// shows, there once "Abruf" is pressed.
		expect(problem.closest('.hidden')).not.toBeNull();
		await user.click(screen.getByText(m.mailbox_part_fetch()).closest('button')!);
		expect(problem.closest('.hidden')).toBeNull();
		expect(problem.parentElement!.textContent).toContain(m.mail_folders());
		failing.clear();
		await user.click(screen.getByRole('button', { name: m.retry() }));
		await vi.waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
		expect(sent.filter((call) => call.path === '/api/v1/users')).toHaveLength(2);
	});

	it('takes at most the folders the API does, and says so (WT2-08)', async () => {
		const user = userEvent.setup();
		const many = Array.from({ length: LIMITS.folders }, (_, n) => `Ordner ${n + 1}`);
		render(MailboxDialog, {
			open: true,
			mailbox: mailboxOf({ folders: many }),
			onsaved: vi.fn()
		});
		await user.click(screen.getByText(m.mailbox_part_fetch()).closest('button')!);
		await user.click(testButton());
		// The test found two folders more (FOUND); with 20 chosen, they cannot be chosen.
		const inbox = within((await screen.findByText(m.mail_folder_inbox())).closest('label')!);
		expect((inbox.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true);
		expect(screen.getByText(m.mail_folders_max({ max: LIMITS.folders }))).toBeTruthy();
	});

	it('keeps what is typed when the page reads the same mailbox anew', async () => {
		const user = userEvent.setup();
		const { rerender } = render(MailboxDialog, { open: true, mailbox: STORED, onsaved: vi.fn() });
		const name = (await screen.findByLabelText(m.field_name())) as HTMLInputElement;
		await user.clear(name);
		await user.type(name, 'Neuer Name');
		await user.type(screen.getByLabelText(m.mail_password()), 'new-secret');
		const loads = () => sent.filter((call) => call.path === '/api/v1/users').length;
		const before = loads();

		// After a fetch or a reconnect of the event stream: the same mailbox, a new object.
		await rerender({ mailbox: { ...STORED } });

		expect((screen.getByLabelText(m.field_name()) as HTMLInputElement).value).toBe('Neuer Name');
		expect((screen.getByLabelText(m.mail_password()) as HTMLInputElement).value).toBe('new-secret');
		// And its choices are not loaded once more.
		expect(loads()).toBe(before);
	});

	it('starts anew for another mailbox', async () => {
		const { rerender } = render(MailboxDialog, { open: true, mailbox: STORED, onsaved: vi.fn() });
		const name = (await screen.findByLabelText(m.field_name())) as HTMLInputElement;
		expect(name.value).toBe(STORED.name);
		await rerender({ mailbox: { ...STORED, id: 'another', name: 'Zweites Postfach' } });
		await vi.waitFor(() =>
			expect((screen.getByLabelText(m.field_name()) as HTMLInputElement).value).toBe(
				'Zweites Postfach'
			)
		);
	});
});
