// The note of a newer Lekto above the tabs of the page System: for admins only, while the release
// is newer than the running one (.knowledge/open/update-notifier-fas.md).
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi, json } from '#lib/testing/api.ts';
import UpdateNotice from './UpdateNotice.svelte';

const RELEASE = 'https://github.com/lektohq/lekto/releases/tag/v0.16.0';

function version(update_available: boolean) {
	return {
		lekto_version: '0.15.6',
		api_version: '0.2',
		update_check: true,
		checked_at: '2026-11-19T21:00:00Z',
		latest: { version: '0.16.0', published_at: '2026-11-19T20:12:00Z', url: RELEASE },
		update_available
	};
}

function signIn(role: 'admin' | 'user') {
	session.start({
		user: { id: role, username: role, role },
		method: 'password',
		expires_at: '2026-11-20T12:00:00Z',
		csrf_token: 'token'
	});
}

afterEach(() => {
	session.clear();
	vi.unstubAllGlobals();
});

describe('the note of a newer Lekto', () => {
	it('tells an admin of the new version with a link to its notes', async () => {
		signIn('admin');
		vi.stubGlobal('fetch', fakeApi({ 'GET /api/v1/version': () => json(version(true)) }));
		render(UpdateNotice);
		expect(await screen.findByText(m.update_title({ version: '0.16.0' }))).toBeTruthy();
		const link = screen.getByRole('link', { name: m.update_release_notes() });
		expect(link.getAttribute('href')).toBe(RELEASE);
		expect(link.getAttribute('target')).toBe('_blank');
		expect(screen.getByText(/0\.15\.6/)).toBeTruthy();
	});

	it('shows nothing without news', async () => {
		signIn('admin');
		const fetchMock = fakeApi({ 'GET /api/v1/version': () => json(version(false)) });
		vi.stubGlobal('fetch', fetchMock);
		render(UpdateNotice);
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
		expect(screen.queryByRole('status')).toBeNull();
	});

	it('shows a user nothing and does not ask', async () => {
		signIn('user');
		const fetchMock = fakeApi({ 'GET /api/v1/version': () => json(version(true)) });
		vi.stubGlobal('fetch', fetchMock);
		render(UpdateNotice);
		await Promise.resolve();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(screen.queryByRole('status')).toBeNull();
	});
});
