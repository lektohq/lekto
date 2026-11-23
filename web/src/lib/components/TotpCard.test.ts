import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi, json, problem } from '#lib/testing/api.ts';
import TotpCard from './TotpCard.svelte';

const SETUP = {
	secret: 'JBSWY3DPEHPK3PXP',
	otpauth_uri: 'otpauth://totp/Lekto:john?secret=JBSWY3DP'
};

// The password first: a session alone sets up no second factor of its own (XA-K03).
describe('TotpCard', () => {
	it('asks for the password before it shows the secret', async () => {
		const sent: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/auth/totp': async (request) => {
					const body = (await request.json()) as { password: string };
					sent.push(body);
					return body.password === 'correct horse battery'
						? json(SETUP, 201)
						: problem(403, { detail: 'the current password is wrong', code: 'wrong_password' });
				}
			})
		);
		const user = userEvent.setup();
		render(TotpCard, { props: { enabled: false, hasPassword: true, onchanged: vi.fn() } });
		await user.click(screen.getByRole('button', { name: m.totp_setup() }));
		const dialog = await screen.findByRole('dialog', { name: m.totp_title() });
		const field = within(dialog).getByLabelText(m.password_current());
		await user.type(field, 'wrong');
		await user.click(within(dialog).getByRole('button', { name: m.totp_setup() }));
		await vi.waitFor(() => expect(dialog.textContent).toContain(m.reason_wrong_password()));
		expect(screen.queryByText(SETUP.secret)).toBeNull();

		await user.clear(field);
		await user.type(field, 'correct horse battery');
		await user.click(within(dialog).getByRole('button', { name: m.totp_setup() }));
		expect((await screen.findByText(SETUP.secret)).textContent).toContain(SETUP.secret);
		expect(sent).toEqual([{ password: 'wrong' }, { password: 'correct horse battery' }]);
	});

	it('offers no setup to an account without a password, and says why', () => {
		vi.stubGlobal('fetch', fakeApi({}));
		render(TotpCard, { props: { enabled: false, hasPassword: false, onchanged: vi.fn() } });
		expect(screen.queryByRole('button', { name: m.totp_setup() })).toBeNull();
		expect(screen.getByText(m.totp_needs_password_hint())).toBeTruthy();
	});
});
