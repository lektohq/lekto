import { describe, expect, it } from 'vitest';
import { byLetter, flipped, matchesWords, searchWords, toggled } from './picking.ts';

describe('toggled', () => {
	it('adds a value once and removes every copy of it', () => {
		expect(toggled(['a'], 'b', true)).toEqual(['a', 'b']);
		expect(toggled(['a', 'b', 'b'], 'b', false)).toEqual(['a']);
	});

	it('leaves the given list as it was', () => {
		const selected = ['a'];
		toggled(selected, 'b', true);
		expect(selected).toEqual(['a']);
	});
});

describe('flipped', () => {
	it('takes a value out when it is in, else adds it', () => {
		expect(flipped(['a', 'b'], 'a')).toEqual(['b']);
		expect(flipped(['b'], 'a')).toEqual(['b', 'a']);
	});
});

describe('searchWords and matchesWords', () => {
	it('match regardless of case and surrounding space', () => {
		const words = searchWords('  Nord ');
		expect(matchesWords('Nord Muster Versicherung', words)).toBe(true);
		expect(matchesWords('nordsee', words)).toBe(true);
		expect(matchesWords('Süd', words)).toBe(false);
	});

	it('match everything without words', () => {
		expect(searchWords('   ')).toBe('');
		expect(matchesWords('anything', '')).toBe(true);
	});
});

describe('byLetter', () => {
	const named = (...labels: string[]) => labels.map((label) => ({ label }));
	const letters = (labels: string[], locale: string) =>
		byLetter(named(...labels), locale).map(
			(group) => `${group.letter}: ${group.items.map((item) => item.label).join(', ')}`
		);

	it('files an umlaut under its plain letter in German: no letter comes twice', () => {
		expect(
			letters(['Auto Muster', 'Zoo Muster', 'Ärztekammer Muster', 'Apotheke Muster'], 'de-DE')
		).toEqual(['A: Apotheke Muster, Ärztekammer Muster, Auto Muster', 'Z: Zoo Muster']);
		// Also when the umlaut comes first in its group.
		expect(letters(['Öl Muster', 'Ost Muster', 'Übung', 'Uhr'], 'de-DE')).toEqual([
			'O: Öl Muster, Ost Muster',
			'U: Übung, Uhr'
		]);
	});

	it('keeps a letter of its own where the language has one', () => {
		// Swedish sorts Ä after Z, as a letter apart.
		expect(letters(['Ärende', 'Avtal', 'Zon'], 'sv-SE')).toEqual([
			'A: Avtal',
			'Z: Zon',
			'Ä: Ärende'
		]);
	});

	it('takes small and capital letters as one, and names the group by the capital', () => {
		expect(letters(['bank muster', 'Bäckerei Muster', 'amt'], 'de-DE')).toEqual([
			'A: amt',
			'B: Bäckerei Muster, bank muster'
		]);
	});

	it('groups digits and names without a letter each by their first sign', () => {
		expect(letters(['24/7 Muster', '2 Muster', ' Muster ', ''], 'de-DE')).toEqual([
			': ',
			'2: 2 Muster, 24/7 Muster',
			'M:  Muster '
		]);
	});

	it('leaves the given list as it was', () => {
		const items = named('B', 'A');
		byLetter(items, 'de-DE');
		expect(items.map((item) => item.label)).toEqual(['B', 'A']);
	});
});
