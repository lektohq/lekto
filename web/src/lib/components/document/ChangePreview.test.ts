import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { formatMoney } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';
import { documentOf } from '#lib/testing/documents.ts';
import ChangePreview from './ChangePreview.svelte';
import { lookupOf } from '#lib/testing/master-data.ts';

type Preview = components['schemas']['DocumentPreviewOut'];

const NET = 'f-net';
const space = (id: string, name: string, members: { user_id: string; role: 'edit' | 'read' }[]) =>
	({ id, name, personal_of: null, description: null, role: 'edit', members }) as never;
const lookup = lookupOf({
	contacts: [],
	documentTypes: [],
	tags: [
		{ id: 't-review', name: 'Review', path: ['Review'] },
		{ id: 't-tax', name: 'Steuer', path: ['Steuer'] }
	],
	fields: [{ id: NET, name: 'Netto', data_type: 'amount' }],
	spaces: [
		space('s-erika', 'Erika', [{ user_id: 'u-erika', role: 'edit' }]),
		space('s-family', 'Familie', [
			{ user_id: 'u-erika', role: 'edit' },
			{ user_id: 'u-john', role: 'read' }
		])
	],
	users: [
		{ id: 'u-erika', username: 'erika', display_name: 'Jane Doe' },
		{ id: 'u-john', username: 'john', display_name: 'John Doe' }
	]
});

const before = documentOf({
	space_id: 's-erika',
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
		expect(screen.getByText('Review').className).toContain('line-through');
		expect(screen.getByText('Steuer').className).not.toContain('line-through');
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
				visibility: { space_id: 's-erika', members: [{ user_id: 'u-erika', role: 'edit' }] }
			})
		});
		expect(screen.getByText(m.dryrun_visible_same({ names: 'Jane Doe' }))).toBeTruthy();
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
						{ user_id: 'u-erika', role: 'edit' },
						{ user_id: 'u-john', role: 'read' }
					]
				}
			})
		});
		expect(screen.getByText(m.dryrun_rules_one())).toBeTruthy();
		expect(screen.getByText(m.dryrun_visible())).toBeTruthy();
		expect(screen.getByText('Familie')).toBeTruthy();
		const john = screen.getByText(m.space_member_reads({ name: 'John Doe' }));
		expect(john.parentElement?.textContent).toContain(m.dryrun_new());
	});
});
