import { afterEach, describe, expect, it, vi } from 'vitest';
import { session } from '#lib/session.svelte.ts';
import { fakeApi, json } from '#lib/testing/api.ts';
import { signIn } from '#lib/testing/session.ts';
import { tokens, tokensChanged } from './tokens.svelte.ts';

const token = (scope: string) => ({ id: scope, name: scope, scope });

function api(list: () => unknown) {
	const fetchMock = fakeApi({ 'GET /api/v1/auth/tokens': list });
	vi.stubGlobal('fetch', fetchMock);
	return fetchMock;
}

afterEach(() => session.clear());

describe('the tokens, read once for all that show them (WC-11)', () => {
	it('asks once however many ask, and again after a change', async () => {
		signIn('user', { id: 'once' });
		const fetchMock = api(() => [token('read')]);
		// The list of the tab and the shortcut's card beside it, in one tick.
		await Promise.all([tokens.load(), tokens.load()]);
		await tokens.load();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(tokens.list).toEqual([token('read')]);
		expect(tokens.hasUploadToken).toBe(false);

		api(() => [token('read'), token('upload')]);
		tokensChanged();
		await tokens.load();
		expect(tokens.hasUploadToken).toBe(true);
	});

	it('reads them anew for another user', async () => {
		signIn('user', { id: 'first' });
		api(() => [token('upload')]);
		await tokens.load();
		expect(tokens.hasUploadToken).toBe(true);
		signIn('user', { id: 'second' });
		const fetchMock = api(() => []);
		await tokens.load();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(tokens.hasUploadToken).toBe(false);
	});

	it('does not know whether one uploads when the read failed, and reads again on request', async () => {
		signIn('user', { id: 'failing' });
		api(() => json({ type: 'about:blank', title: 'Service Unavailable', status: 503 }, 503));
		await tokens.load();
		// One answer for the card and the upload dialog: not known, each says what that means.
		expect(tokens.hasUploadToken).toBeNull();
		expect(tokens.failure).not.toBeNull();
		const fetchMock = api(() => [token('upload')]);
		await tokens.load();
		expect(fetchMock).not.toHaveBeenCalled();
		await tokens.load(true);
		expect(tokens.failure).toBeNull();
		expect(tokens.hasUploadToken).toBe(true);
	});
});
