import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import UserManage from './UserManage.svelte';
import { fakeApi, json } from '#lib/testing/api.ts';
import { choose, selectedValue } from '#lib/testing/select.ts';

vi.mock('$app/navigation', () => ({
	afterNavigate: vi.fn(),
	beforeNavigate: vi.fn(),
	goto: vi.fn()
}));

let fetchMock = fakeApi();

const account = {
	id: 'john',
	username: 'john',
	role: 'user',
	active: true,
	created_at: '2026-10-01T12:00:00Z',
	has_password: true,
	totp_enabled: false,
	linked_accounts: []
};

const profile = {
	user_id: 'john',
	display_name: 'John',
	aliases: [],
	birth_date: null,
	email: null,
	identifiers: [],
	numbers: [
		{ contact_id: 'c1', kind: 'customer_number', value: 'K1', source: 'learned', topic_id: null }
	]
};

beforeEach(() => {
	session.start({
		user: { id: 'erika', username: 'erika', role: 'admin' },
		method: 'password',
		expires_at: '2026-10-14T12:00:00Z',
		csrf_token: 'token'
	});
	fetchMock = fakeApi();
	fetchMock.mockImplementation(async (request) => {
		const path = new URL(request.url).pathname;
		if (request.method === 'PATCH') {
			return json({ ...profile, ...(await request.json()) });
		}
		if (path.endsWith('/users/john')) return json(account);
		if (path.endsWith('/profile')) return json(profile);
		if (path.endsWith('/contacts')) return json([{ id: 'c1', name: 'Insurer', topic_ids: [] }]);
		return json([]);
	});
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
	phone.override(null);
	session.clear();
	vi.unstubAllGlobals();
});

describe('UserManage', () => {
	it('shows the stored role again when the API refuses another (WC-06)', async () => {
		const user = userEvent.setup();
		const patches: unknown[] = [];
		fetchMock.mockImplementation(async (request) => {
			const path = new URL(request.url).pathname;
			if (request.method === 'PATCH') {
				patches.push(await request.json());
				return json(
					{ type: 'about:blank', title: 'Unprocessable', status: 422, detail: 'no' },
					422
				);
			}
			if (path.endsWith('/users/john')) return json(account);
			if (path.endsWith('/profile')) return json(profile);
			return json([]);
		});
		render(UserManage, { open: true, userId: 'john', onchanged: vi.fn() });
		const role = async () => (await screen.findByLabelText(m.user_role())) as HTMLElement;
		expect(selectedValue(await role())).toBe('user');
		await choose(user, await role(), 'admin');
		await vi.waitFor(() => expect(patches).toEqual([{ role: 'admin' }]));
		await vi.waitFor(async () => expect(selectedValue(await role())).toBe('user'));
	});

	it('shows the account in parts, each keeping what was typed', async () => {
		const user = userEvent.setup();
		render(UserManage, { open: true, userId: 'john', onchanged: vi.fn() });
		await screen.findByRole('group', { name: 'john' });
		expect(screen.getByLabelText(m.user_role())).toBeTruthy();
		const count = await screen.findByRole('button', { name: new RegExp(m.profile_numbers()) });
		expect(count.textContent).toContain('1');

		await user.click(screen.getByRole('button', { name: new RegExp(`^${m.profile_title()}`) }));
		const name = screen.getByLabelText(m.profile_display_name()) as HTMLInputElement;
		await user.clear(name);
		await user.type(name, 'John Example');
		await user.click(count);
		// Hidden, not gone: back on the profile, the name typed is still there.
		expect(name.closest('.hidden')).not.toBeNull();
		await user.click(screen.getByRole('button', { name: new RegExp(`^${m.profile_title()}`) }));
		expect(name.closest('.hidden')).toBeNull();
		expect(name.value).toBe('John Example');
	});

	it('is a whole screen on a phone, as every editor, closed with "Fertig"', async () => {
		phone.override(true);
		const user = userEvent.setup();
		const props = $state({ open: true, userId: 'john', onchanged: vi.fn() });
		render(UserManage, props);
		await screen.findByRole('group', { name: 'john' });
		const dialog = screen.getByRole('dialog');
		expect(dialog.className).toContain('h-dvh');
		// Each part saves itself: no form around them, no "Speichern" in the bar.
		expect(dialog.querySelector('form form')).toBeNull();
		const bar = dialog.firstElementChild!.firstElementChild!;
		expect(bar.textContent).toContain(m.picker_done());
		expect(bar.querySelector('button[type="submit"]')).toBeNull();
		await user.click(screen.getByRole('button', { name: m.picker_done() }));
		expect(props.open).toBe(false);
	});
});
