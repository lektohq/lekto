import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { desktop } from '#lib/desktop.svelte.ts';
import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import MasterDataList from './MasterDataList.svelte';
import { fakeApi, masterData } from '#lib/testing/api.ts';
import { testPage } from '#lib/testing/page-state.svelte.ts';
import { goto } from '$app/navigation';

vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));
vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));

let fetchMock: ReturnType<typeof fakeApi>;

const tag = (id: string, path: string[], parent: string | null, scope: string) => ({
	id,
	name: path[path.length - 1],
	path,
	parent_id: parent,
	scope,
	assignment: 'manual',
	shown: false,
	icon: null,
	color: null,
	created_at: '2026-10-17T12:00:00Z'
});

const contact = (id: string, name: string, extra: object = {}) => ({
	id,
	name,
	aliases: [],
	identifiers: [],
	group_ids: [],
	topic_ids: [],
	logo: null,
	logo_failure: null,
	document_count: 0,
	created_at: '2026-10-17T12:00:00Z',
	...extra
});

const CONTACTS = [
	contact('c1', 'Nord Muster Versicherungsgruppe', {
		aliases: ['Nord Muster Krankenversicherung AG', 'Nord Muster Leben AG'],
		group_ids: ['g2'],
		topic_ids: ['p1', 'p2', 'p3'],
		document_count: 104
	}),
	contact('c2', 'Sparkasse Musterstadt', {
		identifiers: [
			{ kind: 'iban', value: 'DE02120300000000202051', source: 'manual', topic_id: null }
		],
		group_ids: ['g3']
	}),
	contact('c3', 'Stadtwerke', { aliases: ['SWM'] })
];

/** The master data the list reads: the contacts and their groups, unless `given` says other. */
function serve(given: Parameters<typeof masterData>[0] = {}) {
	fetchMock = fakeApi(
		masterData({
			contacts: CONTACTS,
			tags: [
				tag('g1', ['Insurer'], null, 'contact'),
				tag('g2', ['Insurer', 'Health insurer'], 'g1', 'contact'),
				tag('g3', ['Bank'], null, 'contact')
			],
			...given
		})
	);
	vi.stubGlobal('fetch', fetchMock);
}

beforeEach(() => {
	testPage.url = new URL('http://lekto/ui/admin/master-data?tab=contacts');
	vi.mocked(goto).mockReset();
	serve();
});

afterEach(() => {
	phone.override(null);
	desktop.override(null);
	localStorage.clear();
	masterDataDialogs.close();
});

describe('MasterDataList', () => {
	it('tells under a contact’s name its groups, aliases, identifiers and topics', async () => {
		render(MasterDataList, { kind: 'contacts' });
		const nord = (await screen.findByText('Nord Muster Versicherungsgruppe')).closest('li')!;
		expect(within(nord).getByText('Health insurer')).toBeTruthy();
		expect(
			within(nord).getByText(
				m.master_alias_more({ alias: 'Nord Muster Krankenversicherung AG', count: 1 })
			)
		).toBeTruthy();
		expect(within(nord).getByText(m.master_topics_many({ count: 3 }))).toBeTruthy();
		const sparkasse = screen.getByText('Sparkasse Musterstadt').closest('li')!;
		expect(within(sparkasse).getByText(m.master_identifier_one())).toBeTruthy();
		expect(
			within(nord).getByRole('link', { name: m.master_documents({ count: '104' }) })
		).toBeTruthy();
	});

	it('finds contacts by alias and by an identifier written with spaces', async () => {
		const { rerender } = render(MasterDataList, { kind: 'contacts', query: 'swm' });
		expect(await screen.findByText('Stadtwerke')).toBeTruthy();
		expect(screen.queryByText('Sparkasse Musterstadt')).toBeNull();
		await rerender({ query: 'DE02 1203 0000' });
		expect(screen.getByText('Sparkasse Musterstadt')).toBeTruthy();
		expect(screen.queryByText('Stadtwerke')).toBeNull();
	});

	it('lists the contacts of a group or one below it, as a link from the Tags tab asks', async () => {
		testPage.url = new URL('http://lekto/ui/admin/master-data?tab=contacts&group=g1');
		render(MasterDataList, { kind: 'contacts' });
		expect(await screen.findByText('Nord Muster Versicherungsgruppe')).toBeTruthy();
		expect(screen.queryByText('Sparkasse Musterstadt')).toBeNull();
		const label = m.master_filter_group({ name: 'Insurer' });
		await fireEvent.click(
			screen.getByRole('button', { name: m.master_filter_remove({ name: label }) })
		);
		expect(vi.mocked(goto)).toHaveBeenCalledWith('?tab=contacts', { reset: false });
	});

	it('ignores a filter that names no tag of its kind, and takes it out of the URL', async () => {
		testPage.url = new URL('http://lekto/ui/admin/master-data?tab=contacts&group=gone');
		render(MasterDataList, { kind: 'contacts' });
		expect(await screen.findByText('Nord Muster Versicherungsgruppe')).toBeTruthy();
		expect(screen.getByText('Sparkasse Musterstadt')).toBeTruthy();
		expect(screen.queryByRole('button', { name: /gone/ })).toBeNull();
		await waitFor(() =>
			expect(vi.mocked(goto)).toHaveBeenCalledWith('?tab=contacts', { replace: true, reset: false })
		);
	});

	it('tells a type’s description under its name, and nothing for a type without one', async () => {
		serve({
			'document-types': [
				{ id: 't1', name: 'Rechnung', description: 'Eine Forderung', group_ids: [], icon: null },
				{ id: 't2', name: 'Kündigung', description: null, group_ids: [], icon: null }
			]
		});
		render(MasterDataList, { kind: 'document-types' });
		const invoice = (await screen.findByText('Rechnung')).closest('li')!;
		expect(within(invoice).getByText('Eine Forderung')).toBeTruthy();
		const notice = screen.getByText('Kündigung').closest('li')!;
		expect(notice.textContent?.replace(/\s+/g, ' ').trim()).toMatch(/^Kündigung\b/);
		expect(within(notice).queryByText(/Beschreibung|description/i)).toBeNull();
	});

	it('on a phone opens a contact with a tap on its row', async () => {
		phone.override(true);
		render(MasterDataList, { kind: 'contacts' });
		const name = await screen.findByText('Nord Muster Versicherungsgruppe');
		expect(
			screen.queryByRole('button', {
				name: m.master_edit({ name: 'Nord Muster Versicherungsgruppe' })
			})
		).toBeNull();
		expect(screen.queryByRole('link')).toBeNull();
		await fireEvent.click(name.closest('button')!);
		expect(masterDataDialogs.request).toMatchObject({ kind: 'contacts', item: { id: 'c1' } });
	});
	it('shows 25 contacts a page, the page the link names, and the first again on a search', async () => {
		const many = Array.from({ length: 30 }, (_, index) =>
			contact(`m${index}`, `Kontakt ${String(index + 1).padStart(2, '0')}`)
		);
		serve({ contacts: many, tags: [] });
		testPage.url = new URL('http://lekto/ui/admin/master-data?tab=contacts&page=2');
		const { rerender } = render(MasterDataList, { kind: 'contacts' });
		expect(await screen.findByText('Kontakt 26')).toBeTruthy();
		expect(screen.queryByText('Kontakt 25')).toBeNull();
		expect(
			screen.getByText(m.pagination_range({ from: '26', to: '30', total: '30' }))
		).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: m.pagination_page({ page: '1' }) }));
		expect(vi.mocked(goto)).toHaveBeenLastCalledWith('?tab=contacts', {});
		vi.mocked(goto).mockReset();
		await rerender({ query: 'Kontakt 0' });
		await waitFor(() =>
			expect(vi.mocked(goto)).toHaveBeenCalledWith('?tab=contacts', { replace: true, reset: false })
		);
	});

	it('puts the contacts with the most documents first when sorted so', async () => {
		serve({
			tags: [],
			contacts: [
				contact('c1', 'Nord', { document_count: 104 }),
				contact('c2', 'Sparkasse', { document_count: 5 }),
				contact('c3', 'Stadtwerke', { document_count: 300 })
			]
		});
		render(MasterDataList, { kind: 'contacts', sort: 'documents' });
		await screen.findByText('Nord');
		const names = screen
			.getAllByText(/^(Nord|Sparkasse|Stadtwerke)$/)
			.map((name) => name.textContent);
		expect(names).toEqual(['Stadtwerke', 'Nord', 'Sparkasse']);
	});

	it('on a desktop lines up a type’s groups and facts, the title pattern in full as tooltip', async () => {
		desktop.override(true);
		serve({
			'document-types': [
				{
					id: 't1',
					name: 'Rechnung',
					description: 'Eine Forderung',
					group_ids: ['g9'],
					icon: null,
					title_pattern: 'Rechnung {{ contact.name }}',
					relation_target: true,
					document_count: 3
				}
			],
			tags: [tag('g9', ['Geld'], null, 'document_type')],
			fields: [
				{ id: 'f1', document_type_ids: ['t1'], required_document_type_ids: ['t1'] },
				{ id: 'f2', document_type_ids: ['t1'], required_document_type_ids: [] },
				{ id: 'f3', document_type_ids: null, required_document_type_ids: [] }
			]
		});
		render(MasterDataList, { kind: 'document-types' });
		const row = (await screen.findByText('Rechnung')).closest('li')!;
		expect(within(row).getByText('Eine Forderung')).toBeTruthy();
		expect(within(row).getByText('Geld')).toBeTruthy();
		const fieldsText = m.master_fields_required({
			fields: m.master_fields_many({ count: 2 }),
			required: m.master_required_count({ count: 1 })
		});
		expect(within(row).getByText(fieldsText)).toBeTruthy();
		expect(within(row).getByText(m.master_title_pattern()).getAttribute('title')).toBe(
			'Rechnung {{ contact.name }}'
		);
		expect(within(row).getByText(m.master_relation_target())).toBeTruthy();
		// Round as a contact's avatar, the shapes of every type where it has no icon.
		expect(row.querySelector('[data-type-avatar]')?.className).toContain('rounded-full');
	});

	it('on a phone tells the first group, how many more, and what the contact is', async () => {
		phone.override(true);
		serve({
			contacts: [contact('c9', 'Finanzamt', { group_ids: ['g1', 'g3'], aliases: ['FA'] })],
			tags: [tag('g1', ['Insurer'], null, 'contact'), tag('g3', ['Bank'], null, 'contact')]
		});
		render(MasterDataList, { kind: 'contacts' });
		const row = (await screen.findByText('Finanzamt')).closest('li')!;
		expect(within(row).getByText('Bank')).toBeTruthy();
		expect(within(row).queryByText('Insurer')).toBeNull();
		expect(within(row).getByText(m.master_groups_more({ count: 1 }))).toBeTruthy();
		expect(within(row).getByText(m.master_alias_short({ alias: 'FA' }))).toBeTruthy();
	});
});
