import { describe, expect, it } from 'vitest';
import { addChips } from '#lib/chips.ts';

const ROOMY = { maxlength: 200, max: 100 };

describe('addChips', () => {
	it('adds each line once, trimmed, and leaves out empty lines and known values', () => {
		expect(addChips(['Nord AG'], ' Nord KV \n\n  \nnord ag\nNord KV', ROOMY)).toEqual({
			values: ['Nord AG', 'Nord KV'],
			left: ''
		});
		expect(addChips([], '', ROOMY)).toEqual({ values: [], left: '' });
		expect(addChips([], 'Meier, Müller & Partner', ROOMY).values).toEqual([
			'Meier, Müller & Partner'
		]);
	});

	it('leaves what is too long or too many', () => {
		expect(addChips(['A'], 'Bb\nCccc\nDd\nEe', { maxlength: 3, max: 3 })).toEqual({
			values: ['A', 'Bb', 'Dd'],
			left: 'Cccc Ee'
		});
	});
});
