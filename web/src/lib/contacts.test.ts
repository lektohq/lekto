import { describe, expect, it } from 'vitest';
import { initials } from './contacts.ts';

describe('initials', () => {
	it.each([
		['Nord Muster Versicherungsgruppe', 'NV'],
		['Stadtwerke Muster', 'SM'],
		['Praxis Dr. Mustermann', 'PM'],
		['Stadtwerke Musterstadt GmbH', 'SM'],
		['Muster', 'M'],
		['ärztekammer musterland', 'ÄM'],
		['Muster & Söhne KG', 'MS'],
		['GmbH', 'G'],
		['24/7 Muster', '2M'],
		['...', '?']
	])('of %s is %s', (name, expected) => {
		expect(initials(name)).toBe(expected);
	});
});
