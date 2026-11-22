import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import FactRows from './FactRows.svelte';
import { lookupOf } from '#lib/testing/master-data.ts';

const BAKERY = '0199a6c4-0000-7000-8000-0000000000c1';
const ERIKA = '0199a6c4-0000-7000-8000-0000000000a1';
const lookup = lookupOf({
	contacts: [{ id: BAKERY, name: 'Muster Bäckerei' }],
	documentTypes: [],
	tags: [],
	spaces: [],
	users: [{ id: ERIKA, username: 'erika', display_name: 'Jane Doe' }]
});

describe('FactRows', () => {
	it('tells what the text names: contacts as chips, identifiers with their contact, persons in brackets', () => {
		render(FactRows, {
			output: {
				named: [{ name: 'Muster Bank' }, { name: 'Muster Bäckerei' }],
				identifiers: [{ kind: 'personnel_number', value: '12345', contact_id: BAKERY }],
				unknown_identifiers: [],
				persons: [{ user_id: ERIKA, strength: 'hard' }]
			},
			lookup
		});
		expect(screen.getByText('Muster Bank')).toBeTruthy();
		expect(screen.getByText(/12345 → Muster Bäckerei$/)).toBeTruthy();
		expect(screen.queryByText(m.signal_unknown_identifiers())).toBeNull();
		expect(screen.getByText(m.signal_person_hard({ name: 'Jane Doe' }))).toBeTruthy();
	});

	it('says when the text names no contact and no identifier', () => {
		render(FactRows, { output: { named: [], identifiers: [] }, lookup });
		expect(screen.getAllByText(m.signal_none())).toHaveLength(2);
		expect(screen.queryByText(m.facts_persons())).toBeNull();
	});
});
