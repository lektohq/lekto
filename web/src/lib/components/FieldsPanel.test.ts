import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import { scope } from '#lib/scope.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import WithDialogs from '#lib/testing/WithDialogs.svelte';
import FieldsPanel from './FieldsPanel.svelte';
import { type Routes, fakeApi, json, noContent } from '#lib/testing/api.ts';
import { fieldOf } from '#lib/testing/master-data.ts';

const INVOICE = '0199a6c4-0000-7000-8000-0000000000e1';
const REMINDER = '0199a6c4-0000-7000-8000-0000000000e2';

let fetchMock: ReturnType<typeof fakeApi>;

const FIELDS = [
	fieldOf({
		id: 'f1',
		name: 'Rechnungsnummer',
		key: 'rechnungsnummer',
		document_type_ids: [INVOICE, REMINDER],
		required_document_type_ids: [INVOICE],
		description: 'Die Nummer, unter der die Rechnung geführt wird'
	}),
	fieldOf({
		id: 'f2',
		name: 'Betrag',
		key: 'betrag',
		data_type: 'amount',
		document_type_ids: [INVOICE],
		position: 5
	})
];

/** The API of the panel: the fields, the types, deleting a field; `more` before these. */
function serve(more: Routes = {}) {
	fetchMock = fakeApi({
		'GET /api/v1/fields': () => FIELDS,
		'GET /api/v1/document-types': () => [
			{ id: INVOICE, name: 'Rechnung', created_at: '2026-10-13T12:00:00Z' },
			{ id: REMINDER, name: 'Mahnung', created_at: '2026-10-13T12:00:00Z' }
		],
		// Saving answers with what was saved.
		'POST /api/v1/fields': () => json({ ...FIELDS[0], id: 'f3' }, 201),
		'PATCH /api/v1/fields/f1': () => FIELDS[0],
		'PATCH /api/v1/fields/f2': () => FIELDS[1],
		'DELETE /api/v1/fields/f1': () => noContent(),
		...more
	});
	vi.stubGlobal('fetch', fetchMock);
}

beforeEach(() => {
	signIn('admin', { id: 'admin', username: 'admin' });
	serve();
});

afterEach(() => {
	masterDataDialogs.close();
	phone.override(null);
	scope.set(false);
	session.clear();
});

describe('FieldsPanel', () => {
	it('lists where a field is required', async () => {
		render(FieldsPanel);
		const required = m.field_def_required_in({ scope: 'Rechnung' });
		expect(await screen.findByText((text) => text.includes(required))).toBeTruthy();
	});

	it('lists the fields as the API orders them and shows a position other than 0', async () => {
		render(FieldsPanel);
		const list = await screen.findByRole('list', { name: m.master_fields() });
		const rows = within(list).getAllByRole('listitem');
		expect(rows.map((row) => row.textContent)).toEqual([
			expect.stringContaining('Rechnungsnummer'),
			expect.stringContaining('Betrag')
		]);
		expect(within(rows[0]).queryByText(/Position/)).toBeNull();
		expect(within(rows[1]).getByText(m.field_def_position_short({ position: '5' }))).toBeTruthy();
	});

	it('moves a field by its position', async () => {
		render(WithDialogs, { component: FieldsPanel });
		await userEvent.click(
			await screen.findByRole('button', { name: m.master_edit({ name: 'Betrag' }) })
		);
		const position = await screen.findByLabelText(m.field_def_position());
		expect((position as HTMLInputElement).value).toBe('5');
		await userEvent.clear(position);
		await userEvent.type(position, '-2');
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const patch = fetchMock.mock.calls
			.map((call) => call[0])
			.find((call) => call.method === 'PATCH');
		expect(await patch?.json()).toMatchObject({ position: -2 });
	});

	// Dialog, tab, search and popover one after another: the longest of these under load.
	it('makes a field required for one of its types', async () => {
		render(WithDialogs, { component: FieldsPanel });
		await screen.findByText('Rechnungsnummer');
		masterDataDialogs.open('fields');
		await userEvent.type(await screen.findByLabelText(m.field_name()), 'Betrag');
		// The types it applies to have a tab of their own.
		await userEvent.click(screen.getByRole('button', { name: new RegExp(`^${m.master_types()}`) }));
		await userEvent.click(screen.getByLabelText(m.field_def_scope_some()));
		expect(screen.getByText(m.field_def_no_type())).toBeTruthy();
		// The types come from a search, each then required or not.
		await userEvent.click(screen.getByRole('button', { name: m.field_def_add_type() }));
		// The popover is placed by measuring, which jsdom does not: its options are found by text.
		await userEvent.click(
			(await screen.findByText('Mahnung', { selector: '[role="option"] span' })).closest(
				'[role="option"]'
			)!
		);
		await userEvent.click(
			screen.getByRole('switch', { name: m.assignment_required_for({ name: 'Mahnung' }) })
		);
		expect(screen.queryByRole('switch', { name: /Rechnung/ })).toBeNull();
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const post = fetchMock.mock.calls.map((call) => call[0]).find((call) => call.method === 'POST');
		expect(await post?.json()).toEqual({
			name: 'Betrag',
			data_type: 'text',
			description: null,
			assignment: 'auto',
			position: 0,
			document_type_ids: [REMINDER],
			required: false,
			required_document_type_ids: [REMINDER]
		});
	});

	it('makes a field of every type required in each document', async () => {
		render(WithDialogs, { component: FieldsPanel });
		masterDataDialogs.open('fields');
		await userEvent.type(await screen.findByLabelText(m.field_name()), 'Datum');
		await userEvent.click(screen.getByRole('button', { name: new RegExp(`^${m.master_types()}`) }));
		expect((screen.getByLabelText(m.field_def_scope_global()) as HTMLInputElement).checked).toBe(
			true
		);
		await userEvent.click(screen.getByRole('switch', { name: m.field_def_required_everywhere() }));
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const post = fetchMock.mock.calls.map((call) => call[0]).find((call) => call.method === 'POST');
		expect(await post?.json()).toMatchObject({
			name: 'Datum',
			document_type_ids: null,
			required: true,
			required_document_type_ids: []
		});
	});

	it('makes a field one that is set by hand only', async () => {
		render(WithDialogs, { component: FieldsPanel });
		masterDataDialogs.open('fields');
		await userEvent.type(await screen.findByLabelText(m.field_name()), 'ASN');
		await userEvent.click(screen.getByLabelText(m.field_def_manual()));
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const post = fetchMock.mock.calls.map((call) => call[0]).find((call) => call.method === 'POST');
		expect(await post?.json()).toMatchObject({ name: 'ASN', assignment: 'manual' });
	});

	it('shows what belongs in a field and lets an admin change it', async () => {
		render(WithDialogs, { component: FieldsPanel });
		const hint = 'Die Nummer, unter der die Rechnung geführt wird';
		expect(await screen.findByText(hint)).toBeTruthy();
		await userEvent.click(
			screen.getByRole('button', { name: m.master_edit({ name: 'Rechnungsnummer' }) })
		);
		// The key templates use stands in the editor.
		expect(within(screen.getByRole('dialog')).getByText('field.rechnungsnummer')).toBeTruthy();
		const description = screen.getByLabelText(m.field_def_description()) as HTMLTextAreaElement;
		expect(description.value).toBe(hint);
		await userEvent.clear(description);
		await userEvent.type(description, 'Rechnungsnummer, nicht die Kundennummer');
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const patch = fetchMock.mock.calls
			.map((call) => call[0])
			.find((call) => call.method === 'PATCH');
		expect(await patch?.json()).toMatchObject({
			description: 'Rechnungsnummer, nicht die Kundennummer'
		});
	});

	it('shows the answer of the newest load, not of the slowest', async () => {
		const field = (name: string) => fieldOf({ id: name, name, key: name.toLowerCase() });
		let slow!: (answer: Response) => void;
		serve({
			// The own fields take their time; those of all users, asked for later, come first.
			'GET /api/v1/fields': (_, url) =>
				url.searchParams.has('all_users')
					? [field('Betrag')]
					: new Promise<Response>((resolve) => (slow = resolve))
		});
		render(FieldsPanel);
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
		scope.set(true);
		expect(await screen.findByText('Betrag')).toBeTruthy();
		slow(json([field('Rechnungsnummer')]));
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(screen.queryByText('Rechnungsnummer')).toBeNull();
		expect(screen.getByText('Betrag')).toBeTruthy();
	});

	it('finds a field by its name, key or description', async () => {
		const { rerender } = render(FieldsPanel, { query: 'kundennummer' });
		expect(await screen.findByText(m.assignment_none_found())).toBeTruthy();
		await rerender({ query: 'geführt' });
		expect(screen.getByText('Rechnungsnummer')).toBeTruthy();
		await rerender({ query: 'field.rechnungs' });
		expect(screen.getByText('Rechnungsnummer')).toBeTruthy();
	});

	it('on a phone opens the editor with a tap on the row, which has no buttons of its own', async () => {
		phone.override(true);
		render(WithDialogs, { component: FieldsPanel });
		const name = await screen.findByText('Rechnungsnummer');
		// No pencil, no bin: the row is the button.
		expect(
			screen.queryByRole('button', { name: m.master_edit({ name: 'Rechnungsnummer' }) })
		).toBeNull();
		expect(
			screen.queryByRole('button', { name: m.master_delete({ name: 'Rechnungsnummer' }) })
		).toBeNull();
		// The key stays in the editor; the row leaves it out.
		expect(screen.queryByText('field.rechnungsnummer')).toBeNull();
		await userEvent.click(name.closest('button')!);
		expect(await screen.findByDisplayValue('Rechnungsnummer')).toBeTruthy();
		expect(screen.getByRole('button', { name: m.editor_save_short() })).toBeTruthy();
	});

	it('deletes a field from its editor, after asking', async () => {
		render(WithDialogs, { component: FieldsPanel });
		await screen.findByText('Rechnungsnummer');
		await userEvent.click(
			screen.getByRole('button', { name: m.master_edit({ name: 'Rechnungsnummer' }) })
		);
		await userEvent.click(
			await screen.findByRole('button', { name: m.master_delete({ name: 'Rechnungsnummer' }) })
		);
		const confirm = await screen.findByRole('alertdialog');
		await userEvent.click(within(confirm).getByRole('button', { name: m.delete_title() }));
		const deleted = fetchMock.mock.calls
			.map((call) => call[0])
			.find((call) => call.method === 'DELETE');
		expect(new URL(deleted!.url).pathname).toBe('/api/v1/fields/f1');
	});
	it('shows 25 fields a page, in their order', async () => {
		serve({
			'GET /api/v1/fields': () =>
				Array.from({ length: 30 }, (_, index) =>
					fieldOf({
						id: `f${index}`,
						name: `Feld ${String(index + 1).padStart(2, '0')}`,
						key: `feld_${index}`
					})
				)
		});
		render(FieldsPanel);
		expect(await screen.findByText('Feld 25')).toBeTruthy();
		expect(screen.queryByText('Feld 26')).toBeNull();
		expect(screen.getByText(m.pagination_range({ from: '1', to: '25', total: '30' }))).toBeTruthy();
	});
});
