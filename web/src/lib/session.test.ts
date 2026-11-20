import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '#lib/api/client.ts';
import { CSRF_HEADER, setSessionHooks } from '#lib/api/fetch.ts';
import { connectSession, session } from './session.svelte.ts';

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

function me(id: string, token: string): Response {
	return new Response(
		JSON.stringify({
			user: { id, username: id, role: 'user' },
			method: 'password',
			expires_at: '2026-10-09T12:00:00Z',
			csrf_token: token,
			lekto_version: '0.8.0'
		}),
		{ status: 200, headers: { 'content-type': 'application/json' } }
	);
}

const stale = () =>
	new Response(
		JSON.stringify({
			type: 'about:blank',
			title: 'Forbidden',
			status: 403,
			detail: `the header ${CSRF_HEADER} is missing or wrong`
		}),
		{ status: 403, headers: { 'content-type': 'application/problem+json' } }
	);

const events = { unauthorized: vi.fn(), replaced: vi.fn() };

beforeEach(() => {
	fetchMock.mockReset();
	events.unauthorized.mockReset();
	events.replaced.mockReset();
	vi.stubGlobal('fetch', fetchMock);
	connectSession(events);
});

afterEach(() => {
	session.clear();
	setSessionHooks(null);
	vi.unstubAllGlobals();
});

describe('loading the session', () => {
	it('keeps the user object while nothing about the user changed', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one')).mockResolvedValueOnce(me('jane', 'two'));
		await session.load();
		const first = session.user;
		await session.load();
		expect(session.user).toBe(first); // effects on `session.user` do not run again
		expect(session.csrfToken).toBe('two');
		fetchMock.mockResolvedValueOnce(me('john', 'three'));
		await session.load();
		expect(session.user).not.toBe(first);
		expect(session.user?.username).toBe('john');
	});

	it('keeps the version of Lekto until the session ends', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		expect(session.version).toBe('0.8.0');
		session.clear();
		expect(session.version).toBeNull();
	});
});

describe('a stale CSRF token', () => {
	it('is fetched anew for the same user, and the change is repeated', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'old'));
		await session.load();
		fetchMock
			.mockResolvedValueOnce(stale())
			.mockResolvedValueOnce(me('jane', 'new'))
			.mockResolvedValueOnce(new Response('{}', { status: 201 }));

		const { response } = await api.POST('/api/v1/spaces', { body: { name: 'Bills' } });

		expect(response.status).toBe(201);
		expect(fetchMock.mock.calls[3][0].headers.get(CSRF_HEADER)).toBe('new');
		expect(events.replaced).not.toHaveBeenCalled();
	});

	it('never repeats a change as someone who signed in in another tab', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'old'));
		await session.load();
		fetchMock.mockResolvedValueOnce(stale()).mockResolvedValueOnce(me('erika', 'theirs'));

		const { response } = await api.POST('/api/v1/spaces', { body: { name: 'Bills' } });

		expect(response.status).toBe(403);
		expect(fetchMock).toHaveBeenCalledTimes(3); // sign-in check, the change, `me`
		expect(events.replaced).toHaveBeenCalledOnce();
	});
});

describe('another user in the same tab', () => {
	const signedIn = (id: string) =>
		({
			user: { id, username: id, role: 'user' },
			method: 'password',
			expires_at: '2026-10-09T12:00:00Z',
			csrf_token: 'token'
		}) as never;

	it('is told apart from the one the tab knew before, also after the session ended', async () => {
		// Each test file starts with a tab that knew no one.
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		expect(session.another).toBe(false);

		session.clear();
		session.start(signedIn('jane'));
		expect(session.another).toBe(false);

		session.clear();
		session.start(signedIn('erika'));
		expect(session.another).toBe(true);

		// Signing in again as the same person is no change.
		session.clear();
		session.start(signedIn('erika'));
		expect(session.another).toBe(false);
	});
});
