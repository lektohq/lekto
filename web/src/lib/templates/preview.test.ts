import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { previewError } from './preview.ts';

describe('why a template is invalid (WD-11)', () => {
	it("says a value templates do not know in the user's language", () => {
		const said = previewError({
			error: 'unknown value contct',
			error_reason: {
				code: 'template_unknown_value',
				params: { value: 'contct' },
				subject: null,
				field: null,
				rule: null
			}
		});
		expect(said).toBe(m.reason_template_unknown_value({ value: 'contct' }));
	});

	it('gives the words of the template engine as they are, and nothing without an error', () => {
		const engine = "invalid template: unknown filter 'nofilter'";
		expect(previewError({ error: engine, error_reason: null })).toBe(engine);
		expect(previewError({ error: null, error_reason: null })).toBeNull();
	});
});
