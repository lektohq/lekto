import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import UserManage from './UserManage.svelte';

vi.mock('$app/navigation', () => ({ beforeNavigate: vi.fn(), goto: vi.fn() }));

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

function json(body: unknown) {
	return new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } });
}

const account = {
	id: 'bob',
	username: 'bob',
	role: 'user',
	active: true,
	created_at: '2026-10-01T12:00:00Z',
	has_password: true,
	totp_enabled: false,
	linked_accounts: []
};

const profile = {
	user_id: 'bob',
	display_name: 'Bob',
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
		user: { id: 'anna', username: 'anna', role: 'admin' },
		method: 'password',
		expires_at: '2026-10-14T12:00:00Z',
		csrf_token: 'token'
	});
	fetchMock.mockReset();
	fetchMock.mockImplementation(async (request) => {
		const path = new URL(request.url).pathname;
		if (request.method === 'PATCH') {
			return json({ ...profile, ...(await request.json()) });
		}
		if (path.endsWith('/users/bob')) return json(account);
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
	it('shows the account in parts, each keeping what was typed', async () => {
		const user = userEvent.setup();
		render(UserManage, { open: true, userId: 'bob', onchanged: vi.fn() });
		await screen.findByRole('group', { name: 'bob' });
		expect(screen.getByLabelText(m.user_role())).toBeTruthy();
		const count = await screen.findByRole('button', { name: new RegExp(m.profile_numbers()) });
		expect(count.textContent).toContain('1');

		await user.click(screen.getByRole('button', { name: new RegExp(`^${m.profile_title()}`) }));
		const name = screen.getByLabelText(m.profile_display_name()) as HTMLInputElement;
		await user.clear(name);
		await user.type(name, 'Bob Example');
		await user.click(count);
		// Hidden, not gone: back on the profile, the name typed is still there.
		expect(name.closest('.hidden')).not.toBeNull();
		await user.click(screen.getByRole('button', { name: new RegExp(`^${m.profile_title()}`) }));
		expect(name.closest('.hidden')).toBeNull();
		expect(name.value).toBe('Bob Example');
	});

	it('is a whole screen on a phone, as every editor, closed with "Fertig"', async () => {
		phone.override(true);
		const user = userEvent.setup();
		const props = $state({ open: true, userId: 'bob', onchanged: vi.fn() });
		render(UserManage, props);
		await screen.findByRole('group', { name: 'bob' });
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
