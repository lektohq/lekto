// The settings: the account and its tabs; what the page loads first.
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { calls, fakeApi, masterData, problem } from '#lib/testing/api.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

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
	});

	it('shows the page once trying again succeeded (WF-02)', async () => {
		// The problem of the first attempt stayed on the page, though the second one loaded all.
		let down = true;
		vi.stubGlobal(
			'fetch',
			fakeApi({
				...masterData(),
				'GET /api/v1/auth/me': () => ME,
				'GET /api/v1/auth/me/profile': () => PROFILE,
				'GET /api/v1/auth/oidc': () =>
					down ? problem(503, { detail: 'boom' }) : { enabled: false, display_name: null }
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

	it('reads the account once after the profile was saved (WF-K05)', async () => {
		const api = fakeApi({
			...masterData(),
			'GET /api/v1/auth/me': () => ME,
			'GET /api/v1/auth/me/profile': () => PROFILE,
			'PATCH /api/v1/auth/me/profile': async (request) => ({
				...PROFILE,
				...((await request.json()) as object)
			}),
			'GET /api/v1/auth/oidc': () => ({ enabled: false, display_name: null })
		});
		vi.stubGlobal('fetch', api);
		const user = userEvent.setup();
		render(Page);
		const name = await screen.findByLabelText(m.profile_display_name());
		await user.clear(name);
		await user.type(name, 'Jane M. Doe');
		const before = api.mock.calls.length;
		await user.click(screen.getByRole('button', { name: m.save() }));
		await waitFor(() => expect(session.user?.display_name).toBe('Jane Doe'));
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(
			calls(api)
				.slice(before)
				.filter((call) => call === 'GET /api/v1/auth/me')
		).toHaveLength(1);
	});

	it('names the profile’s heading by its words alone, the hint beside it (WZ-K04)', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				...masterData(),
				'GET /api/v1/auth/me': () => ME,
				'GET /api/v1/auth/me/profile': () => PROFILE,
				'GET /api/v1/auth/oidc': () => ({ enabled: false, display_name: null })
			})
		);
		goTo('/ui/settings?tab=profile');
		render(Page);
		const heading = await screen.findByRole('heading', { name: m.profile_title() });
		// The hint's button beside the heading: inside, a screen reader reads its name as part of
		// the heading ("Profil Hinweis zu Profil").
		expect(heading.querySelector('button')).toBeNull();
		expect(
			screen.getByRole('button', { name: m.hint_about({ name: m.profile_title() }) })
		).toBeTruthy();
	});
});
