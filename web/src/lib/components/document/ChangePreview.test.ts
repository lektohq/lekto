import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import type { Lookup } from '#lib/masterdata.svelte.ts';
import { formatMoney } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';
import { documentOf } from '#lib/testing/documents.ts';
import ChangePreview from './ChangePreview.svelte';

type Preview = components['schemas']['DocumentPreviewOut'];

const NET = 'f-net';
const space = (id: string, name: string, members: { user_id: string; role: 'edit' | 'read' }[]) =>
	({ id, name, personal_of: null, description: null, role: 'edit', members }) as never;
const lookup = {
	contacts: [],
	documentTypes: [],
	tags: [
		{ id: 't-review', name: 'Review', path: ['Review'] },
		{ id: 't-tax', name: 'Steuer', path: ['Steuer'] }
	],
	fields: [{ id: NET, name: 'Netto', data_type: 'amount' }],
	spaces: [
		space('s-anna', 'Anna', [{ user_id: 'u-anna', role: 'edit' }]),
		space('s-family', 'Familie', [
			{ user_id: 'u-anna', role: 'edit' },
			{ user_id: 'u-max', role: 'read' }
		])
	],
	users: [
		{ id: 'u-anna', username: 'anna', display_name: 'Anna Leider' },
		{ id: 'u-max', username: 'max', display_name: 'Max Muster' }
	]
} as unknown as Lookup;

const before = documentOf({
	space_id: 's-anna',
	tag_ids: ['t-review'],
	fields: { [NET]: { amount: '4152.02', currency: 'EUR' } }
});

function previewOf(changes: Partial<Preview>): Preview {
	return { document: before, changed: [], rules: [], visibility: null, ...changes };
}

describe('ChangePreview', () => {
	it('shows a removed and an added tag, and a value before and after', () => {
		const after = {
			...before,
			tag_ids: ['t-tax'],
			fields: { [NET]: { amount: '4772.70', currency: 'EUR' } }
		};
		render(ChangePreview, {
			before,
			lookup,
			preview: previewOf({ document: after, changed: ['tags', `field:${NET}`] })
		});
		expect(screen.getByText('Review').closest('.line-through')).not.toBeNull();
		expect(screen.getByText('Steuer').closest('.line-through')).toBeNull();
		expect(screen.getByText('Netto')).toBeTruthy();
		expect(screen.getByText(formatMoney('4152.02', 'EUR')).className).toContain('line-through');
		expect(screen.getByText(formatMoney('4772.70', 'EUR'))).toBeTruthy();
	});

	it('says in one line who keeps seeing it while that stays as it was', () => {
		render(ChangePreview, {
			before,
			lookup,
			preview: previewOf({
				changed: ['tags'],
				visibility: { space_id: 's-anna', members: [{ user_id: 'u-anna', role: 'edit' }] }
			})
		});
		expect(screen.getByText(m.dryrun_visible_same({ names: 'Anna Leider' }))).toBeTruthy();
		expect(screen.queryByText(m.dryrun_visible())).toBeNull();
	});

	it('names the new space and who is new when a rule moves it', () => {
		render(ChangePreview, {
			before,
			lookup,
			preview: previewOf({
				changed: ['space'],
				rules: [
					{ rule_id: 'r1', name: 'Steuer in Familie', applied: [], notes: [], sends: [] }
				] as never,
				visibility: {
					space_id: 's-family',
					members: [
						{ user_id: 'u-anna', role: 'edit' },
						{ user_id: 'u-max', role: 'read' }
					]
				}
			})
		});
		expect(screen.getByText(m.dryrun_rules_one())).toBeTruthy();
		expect(screen.getByText(m.dryrun_visible())).toBeTruthy();
		expect(screen.getByText('Familie')).toBeTruthy();
		const max = screen.getByText(m.space_member_reads({ name: 'Max Muster' }));
		expect(max.parentElement?.textContent).toContain(m.dryrun_new());
	});
});
