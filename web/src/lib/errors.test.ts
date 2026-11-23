import { afterEach, describe, expect, it } from 'vitest';
import { ApiError, type Problem } from '#lib/api/problem.ts';
import { problemOf } from '#lib/testing/api.ts';
import { m } from '#lib/paraglide/messages.js';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
import { describeError, describeLoad, fieldErrors } from './errors.ts';

const before = getLocale();
afterEach(() => setLocale(before, { reload: false }));

describe('describeLoad (WF-04)', () => {
	const missing = () => 'This rule does not exist.';

	it('says in the page’s words that the address names nothing, without a retry', () => {
		// Not there or not the caller's to see, and an id the API cannot read.
		for (const status of [404, 422])
			expect(
				describeLoad(
					new ApiError(status, problemOf(status, { detail: 'rule 12345 not found' }), null),
					missing
				)
			).toEqual({
				text: 'This rule does not exist.',
				final: true
			});
	});

	it('gives the API’s reason for what the caller may not, without a retry', () => {
		const failure = describeLoad(
			new ApiError(403, problemOf(403, { detail: 'Admins only.' }), null),
			missing
		);
		expect(failure).toEqual({ text: `${m.error_forbidden()} Admins only.`, final: true });
	});

	it('leaves the retry where trying again can help', () => {
		expect(
			describeLoad(new ApiError(500, problemOf(500, { detail: 'Broken.' }), null), missing)
		).toEqual({
			text: 'Broken.',
			final: false
		});
		expect(describeLoad(new TypeError('Failed to fetch'), missing)).toEqual({
			text: m.error_network(),
			final: false
		});
	});
});

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

	it('says a refused input by its reasons, not in the validation’s English (WG-04)', () => {
		setLocale('de', { reload: false });
		const many = {
			field: 'document_ids',
			message: 'List should have at most 500 items after validation, not 501',
			reason: { code: 'input_too_many', params: { max: 500 } }
		};
		const refused = {
			...problemOf(422, { detail: `document_ids: ${many.message}` }),
			errors: [many, { ...many, field: 'other_ids' }]
		} as unknown as Problem;
		// Each reason once, however many fields share it.
		expect(describeError(new ApiError(422, refused, null))).toBe('Höchstens 500 Einträge.');
		// A reason this UI does not know: the API's sentence, as before.
		const unknown = {
			...refused,
			errors: [{ ...many, reason: { code: 'gizmo', params: {} } }]
		} as unknown as Problem;
		expect(describeError(new ApiError(422, unknown, null))).toBe(refused.detail);
	});

	it('names a missing right', () => {
		expect(describeError(new ApiError(403, problemOf(403, { detail: 'Admins only.' }), null))).toBe(
			`${m.error_forbidden()} Admins only.`
		);
	});

	it('names an unreachable server', () => {
		expect(describeError(new TypeError('Failed to fetch'))).toBe(m.error_network());
		// As Firefox and Safari word it.
		expect(describeError(new TypeError('NetworkError when attempting to fetch resource.'))).toBe(
			m.error_network()
		);
		expect(describeError(new TypeError('Load failed'))).toBe(m.error_network());
		// A fault in the code is no unreachable server (WG-05).
		expect(describeError(new TypeError("Cannot read properties of undefined (reading 'id')"))).toBe(
			m.error_unexpected({ status: 0 })
		);
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
		// The validator's own words are English: a value it refuses without a code of its own says
		// so in the words of the UI (WY-K03).
		expect(fieldErrors(error)).toEqual({
			name: 'Höchstens 200 Zeichen.',
			'field:abc-1': 'Dieser Wert ist ungültig.'
		});
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
