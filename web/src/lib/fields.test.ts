import { afterEach, describe, expect, it } from 'vitest';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
import { emptyValue, isMoney, isPeriod, sameValue, toApi, toInput } from './fields.ts';

describe('field values', () => {
	const before = getLocale();
	afterEach(() => setLocale(before, { reload: false }));

	it('keeps text and trims it', () => {
		expect(toApi('text', '  Hello ')).toBe('Hello');
		expect(toInput('text', 'Hello')).toBe('Hello');
	});

	it('removes a value when the field is empty', () => {
		expect(toApi('text', '  ')).toBeNull();
		expect(toApi('amount', { amount: '', currency: 'EUR' })).toBeNull();
		expect(toApi('boolean', '')).toBeNull();
	});

	it('reads and shows a number in the language of the UI (WG-K05)', () => {
		setLocale('de', { reload: false });
		expect(toApi('number', '1.234,5')).toBe('1234.5');
		expect(toApi('number', '12,5')).toBe('12.5');
		expect(toInput('number', '1234.5')).toBe('1234,5');
		// A dot groups only three digits: one typed out of habit is the decimal point, as the
		// server reads it, not a value a hundred times larger.
		expect(toApi('number', '12.50')).toBe('12.50');
		expect(toApi('amount', { amount: '12.50', currency: 'EUR' })).toEqual({
			amount: '12.50',
			currency: 'EUR'
		});
		expect(toApi('number', '1.234')).toBe('1234');
		expect(toApi('number', '1.234.567,89')).toBe('1234567.89');
		expect(toApi('number', '1 234,5')).toBe('1234.5');
		expect(toApi('number', '-12,5')).toBe('-12.5');
		expect(toApi('number', ',5')).toBe('0.5');
		// What fits no notation goes to the API as typed, which refuses it.
		expect(toApi('number', '1.2.3')).toBe('1.2.3');
		expect(toApi('number', '1.234,5.6')).toBe('1.234,5.6');
		setLocale('en', { reload: false });
		expect(toApi('number', '1,234.5')).toBe('1234.5');
		expect(toApi('number', '1,234')).toBe('1234');
		expect(toApi('number', '12,50')).toBe('12.50');
		expect(toInput('number', '1234.5')).toBe('1234.5');
	});

	it('reads and writes yes/no', () => {
		expect(toInput('boolean', false)).toBe('false');
		expect(toApi('boolean', 'false')).toBe(false);
		expect(toApi('boolean', 'true')).toBe(true);
	});

	it('writes money with an upper-case currency', () => {
		setLocale('de', { reload: false });
		expect(toInput('amount', { amount: '84.20', currency: 'EUR' })).toEqual({
			amount: '84,20',
			currency: 'EUR'
		});
		expect(toApi('amount', { amount: '84,20', currency: 'eur' })).toEqual({
			amount: '84.20',
			currency: 'EUR'
		});
		expect(emptyValue('amount')).toEqual({ amount: '', currency: 'EUR' });
	});

	it('writes a period, one date as that day', () => {
		const september = { start: '2026-09-01', end: '2026-09-30' };
		expect(toInput('period', september)).toEqual(september);
		expect(toApi('period', { start: ' 2026-09-01', end: '2026-09-30 ' })).toEqual(september);
		expect(toApi('period', { start: '2026-09-15', end: '' })).toEqual({
			start: '2026-09-15',
			end: '2026-09-15'
		});
		expect(toApi('period', emptyValue('period'))).toBeNull();
		expect(isPeriod(september) && !isMoney(september)).toBe(true);
		expect(isMoney({ amount: '1', currency: 'EUR' }) && !isPeriod({ amount: '1' })).toBe(true);
	});

	it('compares objects whatever the order of their keys', () => {
		expect(
			sameValue(
				{ start: '2026-09-01', end: '2026-09-30' },
				{ end: '2026-09-30', start: '2026-09-01' }
			)
		).toBe(true);
		expect(
			sameValue(
				{ start: '2026-09-01', end: '2026-09-30' },
				{ start: '2026-09-01', end: '2026-09-29' }
			)
		).toBe(false);
	});

	it('compares values', () => {
		expect(sameValue({ amount: '1', currency: 'EUR' }, { amount: '1', currency: 'EUR' })).toBe(
			true
		);
		expect(sameValue(undefined, null)).toBe(true);
		expect(sameValue('a', 'b')).toBe(false);
	});
});
