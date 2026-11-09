import { afterEach, describe, expect, it, vi } from 'vitest';

const { success, reportError } = vi.hoisted(() => ({ success: vi.fn(), reportError: vi.fn() }));
vi.mock('svelte-sonner', () => ({ toast: { success } }));
vi.mock('#lib/errors.ts', () => ({ reportError }));

import { m } from '#lib/paraglide/messages.js';
import { switchMailbox, switchMailRule, switchRule } from './switch.ts';

afterEach(() => {
	vi.unstubAllGlobals();
	vi.clearAllMocks();
});

function stub(status = 200) {
	const fetch = vi.fn<(request: Request) => Promise<Response>>(
		async () =>
			new Response(JSON.stringify(status === 200 ? { id: 'x', enabled: false } : { title: 'no' }), {
				status,
				headers: { 'content-type': 'application/json' }
			})
	);
	vi.stubGlobal('fetch', fetch);
	return fetch;
}

async function sent(fetch: ReturnType<typeof stub>) {
	const [[request]] = fetch.mock.calls;
	return `${request.method} ${new URL(request.url).pathname} ${await request.text()}`;
}

describe('switching a rule or a mailbox', () => {
	it('changes each kind at its own path and says so', async () => {
		let fetch = stub();
		expect(await switchRule('r1', false)).toEqual({ id: 'x', enabled: false });
		expect(await sent(fetch)).toBe('PATCH /api/v1/rules/r1 {"enabled":false}');
		expect(success).toHaveBeenLastCalledWith(m.rule_switched_off());

		fetch = stub();
		await switchMailRule('m1', true);
		expect(await sent(fetch)).toBe('PATCH /api/v1/mail-rules/m1 {"enabled":true}');
		expect(success).toHaveBeenLastCalledWith(m.rule_switched_on());

		fetch = stub();
		await switchMailbox('b1', true);
		expect(await sent(fetch)).toBe('PATCH /api/v1/mailboxes/b1 {"enabled":true}');
		expect(success).toHaveBeenLastCalledWith(m.mailbox_switched_on());
	});

	it('says what the caller gives in place of the usual words', async () => {
		stub();
		await switchMailRule('m1', true, 'Takes 3 mails.');
		expect(success).toHaveBeenLastCalledWith('Takes 3 mails.');
	});

	it('reports a failure as every error and hands back nothing', async () => {
		stub(409);
		expect(await switchRule('r1', true)).toBeNull();
		expect(reportError).toHaveBeenCalledOnce();
		expect(success).not.toHaveBeenCalled();
	});
});
