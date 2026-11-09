import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi } from '#lib/testing/api.ts';
import Page from './+page.svelte';

const USERS = [
	{
		id: 'u1',
		username: 'anna',
		display_name: 'Anna Busch',
		role: 'admin',
		active: true,
		created_at: '2026-10-01T08:00:00Z'
	},
	{ id: 'u2', username: 'bob', display_name: null, role: 'user', active: false, created_at: null }
];

beforeEach(() => {
	session.start({
		user: { id: 'u1', username: 'anna', role: 'admin' },
		method: 'password',
		expires_at: '2026-10-21T12:00:00Z',
		csrf_token: 'token'
	} as never);
	vi.stubGlobal(
		'fetch',
		fakeApi({
			'GET /api/v1/users': () => USERS,
			'GET /api/v1/users/u2/profile': () => ({
				user_id: 'u2',
				display_name: null,
				aliases: [],
				birth_date: null,
				email: null,
				identifiers: [],
				numbers: []
			}),
			'GET /api/v1/contacts': () => [],
			'GET /api/v1/users/u2': () => ({
				...USERS[1],
				has_password: true,
				totp_enabled: false,
				linked_accounts: []
			})
		})
	);
});

afterEach(() => {
	vi.unstubAllGlobals();
	session.clear();
});

describe('the users', () => {
	it('are a list whose names open the account, a display name before the username', async () => {
		render(Page);
		const rows = await screen.findAllByRole('listitem');
		expect(screen.queryByRole('table')).toBeNull();
		expect(rows).toHaveLength(2);
		expect(within(rows[0]).getByRole('button', { name: 'Anna Busch' })).toBeTruthy();
		expect(rows[0].textContent).toContain('anna');
		expect(rows[0].textContent).toContain(m.role_admin());
		// Without a display name the username is the name.
		await userEvent.click(within(rows[1]).getByRole('button', { name: 'bob' }));
		expect(await screen.findByRole('dialog')).toBeTruthy();
	});
});
