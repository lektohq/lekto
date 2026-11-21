// The settings: the account and its tabs; what the page loads first.
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi, json } from '#lib/testing/api.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => ({
	afterNavigate: vi.fn(),
	beforeNavigate: vi.fn(),
	goto: vi.fn()
}));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

const USER = { id: 'u1', username: 'jane', display_name: 'Jane Doe', role: 'user' };
const ME = {
	user: USER,
	method: 'password',
	expires_at: '2026-11-22T12:00:00Z',
	csrf_token: 'token',
	lekto_version: '0.8.0',
	shortcut_url: null,
	has_password: true,
	totp_enabled: false,
	linked_accounts: []
};
const PROFILE = {
	user_id: 'u1',
	display_name: 'Jane Doe',
	aliases: [],
	birth_date: null,
	email: null,
	identifiers: [],
	numbers: []
};

describe('the settings', () => {
	beforeEach(() => {
		session.start({ ...ME, user: USER } as never);
		goTo('/ui/settings');
	});

	afterEach(() => {
		session.clear();
		vi.unstubAllGlobals();
	});

	it('shows the page once trying again succeeded (WF-02)', async () => {
		// The problem of the first attempt stayed on the page, though the second one loaded all.
		let down = true;
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/auth/me': () => ME,
				'GET /api/v1/auth/me/profile': () => PROFILE,
				'GET /api/v1/auth/oidc': () =>
					down
						? json({ type: 'about:blank', title: 'Unavailable', status: 503, detail: 'boom' }, 503)
						: { enabled: false, display_name: null }
			})
		);
		render(Page);
		expect((await screen.findByRole('alert')).textContent).toContain('boom');
		down = false;
		await userEvent.click(screen.getByRole('button', { name: m.retry() }));
		expect(await screen.findByRole('navigation', { name: m.settings_tabs() })).toBeTruthy();
		expect(screen.queryByRole('alert')).toBeNull();
		expect(screen.queryByText('boom')).toBeNull();
	});
});
