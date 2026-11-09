import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { SHORTCUT_NAME } from '#lib/shortcut.ts';
import { fakeApi } from '#lib/testing/api.ts';
import ShortcutCard from './ShortcutCard.svelte';

function token(scope: 'read' | 'read_write' | 'upload', name = 't') {
	return {
		id: `id-${name}`,
		name,
		scope,
		created_at: '2026-11-06T10:00:00Z',
		expires_at: null,
		last_used_at: null
	};
}

const LINK = 'https://www.icloud.com/shortcuts/abc';

describe('ShortcutCard', () => {
	it('sets the shortcut up: a token that may only upload, then the token, the address and the link', async () => {
		const created: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/auth/tokens': () => [token('read_write')],
				'POST /api/v1/auth/tokens': async (request) => {
					created.push(await request.json());
					return new Response(JSON.stringify({ ...token('upload', 'x'), token: 'lekto_secret' }), {
						status: 201,
						headers: { 'content-type': 'application/json' }
					});
				}
			})
		);
		const user = userEvent.setup();
		render(ShortcutCard, { props: { device: 'iPhone', link: LINK } });
		await user.click(await screen.findByRole('button', { name: m.shortcut_set_up() }));
		await screen.findByText('lekto_secret');
		expect(created).toEqual([
			{ name: m.shortcut_token_name({ device: 'iPhone' }), scope: 'upload', expires_at: null }
		]);
		expect(screen.getByText(window.location.origin)).toBeTruthy();
		expect(screen.getByText(m.shortcut_dialog_text({ name: SHORTCUT_NAME }))).toBeTruthy();
		const add = screen.getByRole('link', { name: m.shortcut_add() });
		expect(add.getAttribute('href')).toBe(LINK);
	});

	it('says it is set up once there is a token that may only upload', async () => {
		vi.stubGlobal('fetch', fakeApi({ 'GET /api/v1/auth/tokens': () => [token('upload')] }));
		render(ShortcutCard, { props: { device: 'Mac', link: LINK } });
		await waitFor(() => expect(screen.getByText(m.shortcut_ready())).toBeTruthy());
		expect(screen.getByRole('button', { name: m.shortcut_another() })).toBeTruthy();
		expect(screen.getByText(m.shortcut_finder_path({ name: SHORTCUT_NAME }))).toBeTruthy();
	});
});
