// The list of webhooks: a switch on each row that takes effect at once, like rules and mailboxes.
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { calls, fakeApi } from '#lib/testing/documents.ts';
import Page from './+page.svelte';

const webhook = {
	id: 'hook',
	owner_id: 'u1',
	name: 'Home Assistant',
	url: 'https://node.example/lekto',
	event_types: ['*'],
	active: true,
	signed: true,
	headers: [],
	body: 'thin',
	body_template: null,
	max_open_tasks: 4,
	model_call: null,
	disabled_reason: null,
	disabled_reasons: [],
	failed_streak: 0,
	previous_secret_valid_until: null,
	created_at: '2026-10-25T10:00:00Z',
	updated_at: '2026-10-25T10:00:00Z'
};

describe('the list of webhooks', () => {
	beforeEach(() => {
		session.start({
			user: { id: 'u1', username: 'tobi', role: 'user' },
			method: 'password',
			expires_at: '2026-10-28T12:00:00Z',
			csrf_token: 'token'
		} as never);
	});

	afterEach(() => {
		session.clear();
		vi.unstubAllGlobals();
	});

	it('pauses a webhook from its row with a switch, not a badge', async () => {
		const bodies: unknown[] = [];
		const api = fakeApi({
			'GET /api/v1/webhooks': () => [webhook],
			'PATCH /api/v1/webhooks/hook': async (request) => {
				bodies.push(await request.json());
				return { ...webhook, active: false };
			}
		});
		vi.stubGlobal('fetch', api);
		render(Page);
		const toggle = await screen.findByRole('switch', {
			name: m.webhook_switch_off({ name: 'Home Assistant' })
		});
		expect(toggle.getAttribute('aria-checked')).toBe('true');
		await userEvent.click(toggle);
		const paused = await screen.findByRole('switch', {
			name: m.webhook_switch_on({ name: 'Home Assistant' })
		});
		expect(paused.getAttribute('aria-checked')).toBe('false');
		expect(calls(api)).toContain('PATCH /api/v1/webhooks/hook');
		expect(bodies).toEqual([{ active: false }]);
	});

	it('leads from no webhook to a new one', async () => {
		vi.stubGlobal('fetch', fakeApi({ 'GET /api/v1/webhooks': () => [] }));
		render(Page);
		expect(await screen.findByText(m.webhook_none())).toBeTruthy();
		// One in the head of the page, one in the note.
		expect(screen.getAllByRole('link', { name: m.webhook_new() })).toHaveLength(2);
	});
});
