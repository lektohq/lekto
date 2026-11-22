import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { FieldDefinition } from '#lib/masterdata.svelte.ts';
import FieldValueInput from './FieldValueInput.svelte';

const field = (data_type: string, choices: string[] = []) =>
	({ id: 'f1', key: 'f1', name: 'Betrag', data_type, choices }) as unknown as FieldDefinition;

/** The text of what the control with `id` is described by. */
const said = () =>
	document.getElementById(
		document.getElementById('field-f1')?.getAttribute('aria-describedby') ?? ''
	)?.textContent;

describe('FieldValueInput (WB-13)', () => {
	it.each([
		['text', 'abc'],
		['number', '12'],
		['amount', { amount: '12', currency: 'EUR' }],
		['boolean', 'true'],
		['choice', 'a'],
		['date', '2026-10-01']
	] as const)('ties the error below a %s field to the field', (type, value) => {
		const { unmount } = render(FieldValueInput, {
			field: field(type, ['a', 'b']),
			value,
			id: 'field-f1',
			error: 'Das passt nicht.'
		});
		expect(screen.getByRole('alert').textContent).toContain('Das passt nicht.');
		expect(said()).toContain('Das passt nicht.');
		unmount();
	});

	it('names nothing to describe a field without an error', () => {
		render(FieldValueInput, { field: field('text'), value: 'abc', id: 'field-f1' });
		expect(document.getElementById('field-f1')?.hasAttribute('aria-describedby')).toBe(false);
	});
});
