import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { flagLabel, importanceLabel, isKeyword, keywordOptions } from './mail-traits.ts';

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
