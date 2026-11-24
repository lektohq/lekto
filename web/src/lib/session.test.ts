import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '#lib/api/client.ts';
import { CSRF_HEADER, setSessionHooks } from '#lib/api/fetch.ts';
import { json, problem } from '#lib/testing/api.ts';
import { meOf } from '#lib/testing/session.ts';
import { connectSession, recheckSession, session } from './session.svelte.ts';

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

function me(id: string, token: string): Response {
	return json(meOf({ user: { id, username: id, role: 'user' }, csrf_token: token }));
}

const stale = () =>
	json(
		{
			type: 'about:blank',
			title: 'Forbidden',
			status: 403,
			detail: `the header ${CSRF_HEADER} is missing or wrong`,
			reason: { code: 'csrf_missing', params: { header: CSRF_HEADER } }
		},
		403
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

describe('a proxy answering for a Lekto that is not there', () => {
	// WH-01: Caddy, nginx and Traefik answer 502 while the API restarts. That is no sign-out.
	const gateway = () => new Response('Bad Gateway', { status: 502 });

	it('keeps user and token when the session cannot be read', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		const user = session.user;
		fetchMock.mockResolvedValueOnce(gateway());

		await expect(session.load()).rejects.toMatchObject({ status: 502 });

		expect(session.user).toBe(user);
		expect(session.csrfToken).toBe('one');
		expect(session.version).toBe('0.8.0');
	});

	it('ends the session only on the word of the API', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		fetchMock.mockResolvedValueOnce(problem(401));

		expect(await session.load()).toBeNull(); // no account: nothing to show (WF-K05)

		expect(session.user).toBeNull();
		expect(session.csrfToken).toBeNull();
	});

	it('leaves the app as it is when the stream asks who is signed in', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		fetchMock.mockResolvedValueOnce(gateway());

		await recheckSession();

		expect(session.user?.id).toBe('jane');
		expect(events.unauthorized).not.toHaveBeenCalled();
		expect(events.replaced).not.toHaveBeenCalled();
	});

	it('stays signed in while the server did not sign out', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));
		await session.load();
		fetchMock.mockResolvedValueOnce(gateway());

		await expect(session.logout()).rejects.toMatchObject({ status: 502 });

		expect(session.user?.id).toBe('jane');
		expect(session.csrfToken).toBe('one');
	});

	it('forgets the session once the server signed out, or says it has gone', async () => {
		for (const answer of [() => new Response(null, { status: 204 }), () => problem(401)]) {
			fetchMock.mockResolvedValueOnce(me('jane', 'one'));
			await session.load();
			fetchMock.mockResolvedValueOnce(answer());
			await session.logout();
			expect(session.user).toBeNull();
			expect(session.csrfToken).toBeNull();
		}
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

describe('asking anew who is signed in', () => {
	const gone = () => problem(401);

	async function signedInAs(id: string) {
		fetchMock.mockResolvedValueOnce(me(id, 'one'));
		await session.load();
	}

	it('changes nothing while the same user is signed in', async () => {
		await signedInAs('jane');
		const user = session.user;
		fetchMock.mockResolvedValueOnce(me('jane', 'two'));

		await recheckSession();

		expect(session.user).toBe(user);
		expect(session.csrfToken).toBe('two');
		expect(events.replaced).not.toHaveBeenCalled();
		expect(events.unauthorized).not.toHaveBeenCalled();
	});

	it('follows the same user whose role changed, without starting afresh', async () => {
		await signedInAs('jane');
		fetchMock.mockResolvedValueOnce(
			json({
				user: { id: 'jane', username: 'jane', role: 'admin' },
				method: 'password',
				expires_at: '2026-10-09T12:00:00Z',
				csrf_token: 'two',
				lekto_version: '0.8.0'
			})
		);

		await recheckSession();

		expect(session.isAdmin).toBe(true);
		expect(events.replaced).not.toHaveBeenCalled();
	});

	it('starts afresh when another user holds the session now', async () => {
		await signedInAs('jane');
		fetchMock.mockResolvedValueOnce(me('erika', 'theirs'));

		await recheckSession();

		expect(events.replaced).toHaveBeenCalledTimes(1);
		expect(events.unauthorized).not.toHaveBeenCalled();
	});

	it('leads to signing in when the session is gone', async () => {
		await signedInAs('jane');
		fetchMock.mockResolvedValueOnce(gone());

		await recheckSession();

		expect(session.user).toBeNull();
		expect(events.unauthorized).toHaveBeenCalledTimes(1);
		expect(events.replaced).not.toHaveBeenCalled();
	});

	it('keeps the user while the API is not reachable', async () => {
		await signedInAs('jane');
		fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

		await expect(recheckSession()).resolves.toBeUndefined();

		expect(session.user?.id).toBe('jane');
		expect(events.replaced).not.toHaveBeenCalled();
		expect(events.unauthorized).not.toHaveBeenCalled();
	});

	it('asks once when two occasions come together', async () => {
		await signedInAs('jane');
		fetchMock.mockResolvedValue(me('erika', 'theirs'));

		await Promise.all([recheckSession(), recheckSession()]);

		// One request beside the one that signed in, one fresh start.
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(events.replaced).toHaveBeenCalledTimes(1);
	});

	it('tells no one when nobody was signed in before', async () => {
		fetchMock.mockResolvedValueOnce(me('jane', 'one'));

		await recheckSession();

		expect(session.user?.id).toBe('jane');
		expect(events.replaced).not.toHaveBeenCalled();
	});
});
