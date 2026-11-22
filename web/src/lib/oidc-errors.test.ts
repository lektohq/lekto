import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { oidcErrorMessage } from './oidc-errors.ts';

describe('oidcErrorMessage', () => {
	it('has a text for every code of the API', () => {
		// The codes the API puts in the address (`_oidc_failure` in `rest/account.py`); the
		// OpenAPI document does not list them.
		expect(oidcErrorMessage('denied')).toBe(m.oidc_error_denied());
		expect(oidcErrorMessage('failed')).toBe(m.oidc_error_failed());
		expect(oidcErrorMessage('conflict')).toBe(m.oidc_error_conflict());
		expect(oidcErrorMessage('provider')).toBe(m.oidc_error_provider());
	});

	it('ignores anything else', () => {
		expect(oidcErrorMessage(null)).toBeNull();
		expect(oidcErrorMessage('<script>')).toBeNull();
	});
});
