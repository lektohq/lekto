import { afterEach, describe, expect, it } from 'vitest';
import { ApiError, type Problem } from '#lib/api/problem.ts';
import { problemOf } from '#lib/testing/api.ts';
import { m } from '#lib/paraglide/messages.js';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
import { describeError, fieldErrors } from './errors.ts';

const before = getLocale();
afterEach(() => setLocale(before, { reload: false }));

describe('describeError', () => {
	it('keeps the detail of the API', () => {
		expect(describeError(new ApiError(409, problemOf(409, { detail: 'Name taken.' }), null))).toBe(
			'Name taken.'
		);
		expect(describeError(new ApiError(409, problemOf(409, { detail: null }), null))).toBe(
			'Conflict'
		);
	});

	it('tells how long to wait', () => {
		expect(describeError(new ApiError(429, problemOf(429), 12))).toBe(
			m.error_too_many({ seconds: 12 })
		);
		expect(describeError(new ApiError(429, null, null))).toBe(m.error_too_many_later());
	});

	it('gives a reason with a code in the user language', () => {
		setLocale('de', { reload: false });
		const taken = problemOf(409, {
			detail: "'Invoice' already exists",
			code: 'name_taken',
			params: { name: 'Invoice' }
		});
		expect(describeError(new ApiError(409, taken, null))).toBe('„Invoice“ gibt es schon.');
		const unknown = { ...taken, reason: { code: 'from_the_future', params: {} } };
		expect(describeError(new ApiError(409, unknown as Problem, null))).toBe(
			"'Invoice' already exists"
		);
	});

	it('names a missing right', () => {
		expect(describeError(new ApiError(403, problemOf(403, { detail: 'Admins only.' }), null))).toBe(
			`${m.error_forbidden()} Admins only.`
		);
	});

	it('names an unreachable server', () => {
		expect(describeError(new TypeError('Failed to fetch'))).toBe(m.error_network());
	});

	it('falls back to the status', () => {
		expect(describeError(new ApiError(418, null, null))).toBe(m.error_unexpected({ status: 418 }));
	});

	it('names an unreachable server when a proxy answers for it', () => {
		// WM-01: 502, 503 and 504 without problem details come from the proxy in front.
		// Traefik answers a plain 500 while its service is empty: any 5xx without them.
		for (const status of [500, 502, 503, 504]) {
			expect(describeError(new ApiError(status, null, null))).toBe(m.error_network());
		}
	});

	it('keeps what Lekto itself says with a 500', () => {
		expect(
			describeError(new ApiError(500, problemOf(500, { detail: 'Something broke.' }), null))
		).toBe('Something broke.');
	});

	it('keeps what the API itself says with a 503', () => {
		expect(
			describeError(new ApiError(503, problemOf(503, { detail: 'No search configured.' }), null))
		).toBe('No search configured.');
	});
});

describe('fieldErrors', () => {
	it('splits a 422 by field', () => {
		const error = new ApiError(
			422,
			problemOf(422, {
				detail: 'title: String should have at least 1 character; fields.abc-1: bad value'
			}),
			null
		);
		expect(fieldErrors(error)).toEqual({
			title: 'String should have at least 1 character',
			'field:abc-1': 'bad value'
		});
	});

	it('gives each part with a code in the user language', () => {
		setLocale('de', { reload: false });
		const error = new ApiError(
			422,
			problemOf(422, {
				errors: [
					{
						field: 'name',
						code: 'input_too_long',
						params: { max: 200 },
						message: 'String should have at most 200 characters'
					},
					{
						field: 'fields.abc-1',
						code: 'input_invalid',
						params: { detail: 'odd' },
						message: 'odd'
					}
				]
			}),
			null
		);
		expect(fieldErrors(error)).toEqual({ name: 'Höchstens 200 Zeichen.', 'field:abc-1': 'odd' });
	});

	it('is empty for other errors', () => {
		expect(fieldErrors(new ApiError(409, problemOf(409, { detail: 'title: x' }), null))).toEqual(
			{}
		);
		expect(fieldErrors(new Error('x'))).toEqual({});
		expect(
			fieldErrors(new ApiError(422, problemOf(422, { detail: 'Name is taken.' }), null))
		).toEqual({});
	});
});
