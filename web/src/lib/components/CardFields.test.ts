import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { cardLines } from '#lib/card-fields.ts';
import type { FieldDefinition } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import CardFields from './CardFields.svelte';

const TODAY = new Date(2026, 9, 20, 15, 30); // 20 October 2026, afternoon

function field(id: string, name: string, data_type: string): FieldDefinition {
	return { id, name, data_type } as unknown as FieldDefinition;
}

const AMOUNT = field('a', 'Betrag', 'amount');
const DUE = field('d', 'Fällig am', 'date');

describe('CardFields', () => {
	it('marks a passed deadline with words and an icon, not colour alone', () => {
		const lines = cardLines(
			{ a: { amount: '89.00', currency: 'EUR' }, d: '2026-10-16' },
			[AMOUNT, DUE],
			'd',
			TODAY
		);
		const { container } = render(CardFields, { lines });
		expect(screen.getByText(m.due_overdue({ count: '4' }), { exact: false })).toBeTruthy();
		expect(container.querySelector('svg')).not.toBeNull();
		expect(container.textContent).toContain('Fällig am:');
	});
});
