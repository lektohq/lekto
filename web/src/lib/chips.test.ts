import { describe, expect, it } from 'vitest';
import { addChips } from '#lib/chips.ts';

const ROOMY = { maxlength: 200, max: 100 };

describe('addChips', () => {
	it('adds each line once, trimmed, and leaves out empty lines and known values', () => {
		expect(addChips(['Muster AG'], ' Muster KV \n\n  \nmuster ag\nMuster KV', ROOMY)).toEqual({
			values: ['Muster AG', 'Muster KV'],
			left: ''
		});
		expect(addChips([], '', ROOMY)).toEqual({ values: [], left: '' });
		expect(addChips([], 'Mustermann, Muster & Partner', ROOMY).values).toEqual([
			'Mustermann, Muster & Partner'
		]);
	});

	it('leaves what is too long or too many', () => {
		expect(addChips(['A'], 'Bb\nCccc\nDd\nEe', { maxlength: 3, max: 3 })).toEqual({
			values: ['A', 'Bb', 'Dd'],
			left: 'Cccc Ee'
		});
	});
});
