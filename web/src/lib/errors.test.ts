import { afterEach, describe, expect, it } from 'vitest';
import { ApiError, type Problem } from '#lib/api/problem.ts';
import { m } from '#lib/paraglide/messages.js';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
import { describeError, describeLoad, fieldErrors } from './errors.ts';

const before = getLocale();
afterEach(() => setLocale(before, { reload: false }));

const problem = (status: number, detail: string | null = null): Problem => ({
	type: 'about:blank',
	title: 'Title',
	status,
	detail,
	existing_document_id: null,
	space_id: null,
	open_fields: null,
	blocking_spaces: null,
	second_factor_required: null,
	reason: null,
	errors: null
});

describe('describeLoad (WF-04)', () => {
	const missing = () => 'This rule does not exist.';

	it('says in the page’s words that the address names nothing, without a retry', () => {
		// Not there or not the caller's to see, and an id the API cannot read.
		for (const status of [404, 422])
			expect(
				describeLoad(new ApiError(status, problem(status, 'rule 12345 not found'), null), missing)
			).toEqual({
				text: 'This rule does not exist.',
				final: true
			});
	});

	it('gives the API’s reason for what the caller may not, without a retry', () => {
		const failure = describeLoad(new ApiError(403, problem(403, 'Admins only.'), null), missing);
		expect(failure).toEqual({ text: `${m.error_forbidden()} Admins only.`, final: true });
	});

	it('leaves the retry where trying again can help', () => {
		expect(describeLoad(new ApiError(500, problem(500, 'Broken.'), null), missing)).toEqual({
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
		expect(describeError(new ApiError(409, problem(409, 'Name taken.'), null))).toBe('Name taken.');
		expect(describeError(new ApiError(409, problem(409), null))).toBe('Title');
	});

	it('tells how long to wait', () => {
		expect(describeError(new ApiError(429, problem(429), 12))).toBe(
			m.error_too_many({ seconds: 12 })
		);
		expect(describeError(new ApiError(429, null, null))).toBe(m.error_too_many_later());
	});

	it('gives a reason with a code in the user language', () => {
		setLocale('de', { reload: false });
		const taken = {
			...problem(409, "'Invoice' already exists"),
			reason: { code: 'name_taken' as const, params: { name: 'Invoice' } }
		};
		expect(describeError(new ApiError(409, taken, null))).toBe('„Invoice“ gibt es schon.');
		const unknown = { ...taken, reason: { code: 'from_the_future', params: {} } };
		expect(describeError(new ApiError(409, unknown as Problem, null))).toBe(
			"'Invoice' already exists"
		);
	});

	it('names a missing right', () => {
		expect(describeError(new ApiError(403, problem(403, 'Admins only.'), null))).toBe(
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
		expect(describeError(new ApiError(500, problem(500, 'Something broke.'), null))).toBe(
			'Something broke.'
		);
	});

	it('keeps what the API itself says with a 503', () => {
		expect(describeError(new ApiError(503, problem(503, 'No search configured.'), null))).toBe(
			'No search configured.'
		);
	});
});

describe('fieldErrors', () => {
	it('splits a 422 by field', () => {
		const error = new ApiError(
			422,
			problem(422, 'title: String should have at least 1 character; fields.abc-1: bad value'),
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
			{
				...problem(422, 'name: String should have at most 200 characters; fields.abc-1: odd'),
				errors: [
					{
						field: 'name',
						message: 'String should have at most 200 characters',
						reason: { code: 'input_too_long', params: { max: 200 } }
					},
					{
						field: 'fields.abc-1',
						message: 'odd',
						reason: { code: 'input_invalid', params: { detail: 'odd' } }
					}
				]
			},
			null
		);
		expect(fieldErrors(error)).toEqual({ name: 'Höchstens 200 Zeichen.', 'field:abc-1': 'odd' });
	});

	it('is empty for other errors', () => {
		expect(fieldErrors(new ApiError(409, problem(409, 'title: x'), null))).toEqual({});
		expect(fieldErrors(new Error('x'))).toEqual({});
		expect(fieldErrors(new ApiError(422, problem(422, 'Name is taken.'), null))).toEqual({});
	});
});
