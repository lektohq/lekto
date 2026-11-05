import { describe, expect, it } from 'vitest';
import openapi from '../../openapi.json';
import { m } from '#lib/paraglide/messages.js';
import {
	flagLabel,
	importanceLabel,
	isKeyword,
	keywordOptions,
	MAIL_FIELD_OPERATORS
} from './mail-traits.ts';

const operators = (openapi as unknown as { 'x-mail-operators': Record<string, string[]> })[
	'x-mail-operators'
];

describe('the fields of a mail', () => {
	it('take the operators the API takes for each, in the order of the UI', () => {
		expect(Object.keys(MAIL_FIELD_OPERATORS).sort()).toEqual(Object.keys(operators).sort());
		for (const [field, ops] of Object.entries(operators)) {
			expect(
				[...MAIL_FIELD_OPERATORS[field as keyof typeof MAIL_FIELD_OPERATORS]].sort(),
				field
			).toEqual([...ops].sort());
		}
	});
});

describe('the marks of a mail', () => {
	it('names importance and flag colours in the words of the UI', () => {
		expect(importanceLabel('low')).toBe(m.mail_importance_low());
		expect(flagLabel('purple')).toBe(m.mail_flag_purple());
		expect(flagLabel('pink')).toBe('pink');
	});

	it('takes a keyword IMAP can carry', () => {
		expect(['Lekto', '$label1', 'a-b_c'].every(isKeyword)).toBe(true);
		expect(['', 'zwei Wörter', 'Größe', 'a]', 'x*', 'a'.repeat(101)].some(isKeyword)).toBe(false);
	});

	it('offers the known keywords and keeps one chosen before', () => {
		expect(keywordOptions(['Lekto'], 'Alt').map((option) => option.value)).toEqual([
			'Lekto',
			'Alt'
		]);
		expect(keywordOptions(['Lekto'], 'Lekto')).toHaveLength(1);
	});
});
