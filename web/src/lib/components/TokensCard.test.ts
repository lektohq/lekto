import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi, json } from '#lib/testing/api.ts';
import { signIn } from '#lib/testing/session.ts';
import { tokensChanged } from '#lib/tokens.svelte.ts';
import TokensCard from './TokensCard.svelte';

const created: unknown[] = [];

beforeEach(() => {
	// The tokens are read once for all that show them (`lib/tokens.svelte.ts`).
	tokensChanged();
	created.length = 0;
	signIn('user', { id: 'jane', username: 'jane' });
	vi.stubGlobal(
		'fetch',
		fakeApi({
			'GET /api/v1/auth/tokens': () => [],
			'POST /api/v1/auth/tokens': async (request) => {
				created.push(await request.json());
				return json(
					{
						id: 't1',
						name: 'Skript',
						scope: 'read',
						rights: [],
						created_at: '2026-11-06T10:00:00Z',
						expires_at: null,
						last_used_at: null,
						token: 'lekto_secret'
					},
					201
				);
			}
		})
	);
});

afterEach(() => session.clear());

describe('TokensCard', () => {
	it('marks what is missing when a new token is sent without it, its button active (WZ-K09)', async () => {
		const user = userEvent.setup();
		render(TokensCard);
		await user.click(await screen.findByRole('button', { name: m.token_new() }));
		const dialog = await screen.findByRole('dialog');
		const create = within(dialog).getByRole('button', { name: m.create() }) as HTMLButtonElement;
		expect(create.disabled).toBe(false);
		await user.click(create);
		expect(created).toEqual([]);
		expect(await within(dialog).findByText(m.form_invalid())).toBeTruthy();
		const name = within(dialog).getByLabelText(m.field_name());
		expect(name.getAttribute('aria-invalid')).toBe('true');
		expect(document.activeElement).toBe(name);
		await user.type(name, 'Skript');
		await user.click(create);
		expect(await screen.findByText('lekto_secret')).toBeTruthy();
		expect(created).toEqual([{ name: 'Skript', scope: 'read', expires_at: null }]);
	});
});
