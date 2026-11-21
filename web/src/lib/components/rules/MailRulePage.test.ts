// The editor of a mail rule as a page: it loads, checks and saves the way of every rule.
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { m } from '#lib/paraglide/messages.js';
import { calls, fakeApi, json } from '#lib/testing/api.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import MailRulePage from './MailRulePage.svelte';

vi.mock('$app/navigation', () => ({
	afterNavigate: vi.fn(),
	beforeNavigate: vi.fn(),
	goto: vi.fn()
}));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

const RULE = {
	id: 'r1',
	mailbox_id: 'm1',
	name: 'Strom',
	priority: 1,
	conditions: { all: [{ field: 'sender', op: 'ends_with', value: '@stadtwerke.example' }] },
	parts: 'all',
	user_id: 'u1',
	space_id: null,
	text_type_id: null,
	after: [],
	enabled: true,
	disabled_reason: null,
	created_at: '2026-11-04T10:00:00Z',
	updated_at: '2026-11-04T10:00:00Z'
};

function serve(patch: () => unknown) {
	const api = fakeApi({
		'GET /api/v1/mail-rules/r1': () => RULE,
		'GET /api/v1/mailboxes': () => [
			{ id: 'm1', name: 'Household', folders: ['INBOX'], status: { keywords: [] } }
		],
		'GET /api/v1/users': () => [
			{ id: 'u1', username: 'erika', display_name: 'Erika Mustermann', active: true }
		],
		'GET /api/v1/spaces': () => [],
		'GET /api/v1/document-types': () => [],
		'PATCH /api/v1/mail-rules/r1': patch
	});
	vi.stubGlobal('fetch', api);
	return api;
}

afterEach(() => {
	vi.unstubAllGlobals();
	vi.clearAllMocks();
});

describe('the editor of a mail rule, as a page', () => {
	it('shows what the API refuses at the condition it names (WD-05)', async () => {
		goTo('/ui/rules/mail/r1/edit', { id: 'r1' });
		serve(() =>
			json(
				{
					type: 'about:blank',
					title: 'Unprocessable',
					status: 422,
					detail: "conditions.all[0]: operator 'ends_with' does not apply to folder"
				},
				422
			)
		);
		render(MailRulePage, { id: 'r1' });
		await userEvent.click(await screen.findByRole('button', { name: m.rule_save() }));

		const value = await screen.findByLabelText(m.rule_condition_value());
		await waitFor(() => expect(value.getAttribute('aria-invalid')).toBe('true'));
		expect(screen.getByText("operator 'ends_with' does not apply to folder")).toBeTruthy();
		// Above the buttons only that something is wrong, not the API's place.
		expect(screen.getByText(m.rule_form_invalid())).toBeTruthy();
		expect(screen.queryByText(/conditions\.all/)).toBeNull();
		expect(goto).not.toHaveBeenCalled();
	});

	it('saves switched off and goes on to the dry run', async () => {
		goTo('/ui/rules/mail/r1/edit', { id: 'r1' });
		const api = serve(() => RULE);
		render(MailRulePage, { id: 'r1' });
		await userEvent.click(await screen.findByRole('button', { name: m.rule_save() }));
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/ui/rules/mail/r1/apply?saved=1'));
		const sent = api.mock.calls.find(([request]) => request.method === 'PATCH')![0];
		expect((await sent.json()).enabled).toBe(false);
		expect(calls(api)).toContain('PATCH /api/v1/mail-rules/r1');
	});
});
