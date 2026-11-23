import { fireEvent, render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { apiQuery, NO_FILTERS } from '#lib/filters.ts';
import { formatNumber } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';
import { calls, fakeApi } from '#lib/testing/api.ts';
import StreamView from './StreamView.svelte';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import { settled } from '#lib/testing/time.ts';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

const doc = (id: string, date: string, lane: string | null = 'green') => ({
	id,
	title: `Abschlag ${id}`,
	document_date: date,
	created_at: `${date}T10:00:00Z`,
	contact_id: 'c1',
	document_type_id: 't1',
	lane
});

const series = (documents: object[], changes: object = {}) => ({
	kind: 'series',
	documents,
	contact_id: 'c1',
	document_type_id: 't1',
	number: 'V-1',
	target: null,
	expected: null,
	parent: null,
	joins: null,
	folded: false,
	...changes
});

describe('StreamView', () => {
	beforeEach(() => goTo('/ui/documents'));

	it('shows the lanes on the months with the target and the expected document', async () => {
		const api = fakeApi({
			'GET /api/v1/documents/stream': () => ({
				lanes: [
					series([doc('a', '2026-07-15'), doc('b', '2026-08-15')], {
						target: doc('v', '2026-06-01'),
						expected: {
							next_date: '2026-09-15',
							next_period: null,
							state: 'overdue',
							cadence: 'monthly',
							spread_days: 2
						}
					})
				],
				truncated: true
			})
		});
		vi.stubGlobal('fetch', api);
		const query = { ...apiQuery({ ...NO_FILTERS, contacts: ['c1'] }) };
		render(StreamView, { props: { query, lookup: null } });
		const table = await screen.findByRole('table', { name: m.stream_lanes() });
		expect(within(table).getAllByRole('columnheader')).toHaveLength(5); // lanes + 4 months
		expect(within(table).getByRole('link', { name: /Abschlag v/ })).toBeTruthy();
		expect(within(table).getByText(/V-1/)).toBeTruthy();
		expect(screen.getByText(m.stream_truncated())).toBeTruthy();
		expect(calls(api)).toContain('GET /api/v1/documents/stream?contact_id=c1');
	});

	it('folds a stretch without documents and marks a document in processing', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/documents/stream': () => ({
					lanes: [
						series([doc('a', '2026-07-15'), doc('p', '2026-08-15', null)], {
							target: doc('v', '2021-06-01')
						})
					],
					truncated: false
				})
			})
		);
		render(StreamView, { props: { query: apiQuery(NO_FILTERS), lookup: null } });
		const table = await screen.findByRole('table', { name: m.stream_lanes() });
		const gap = m.stream_gap({ count: formatNumber(60) }); // 2021-07 to 2026-06
		expect(within(table).getByRole('columnheader', { name: gap })).toBeTruthy();
		expect(within(table).getAllByRole('columnheader')).toHaveLength(5); // lanes, 06/21, gap, 07, 08
		expect(within(table).getByRole('link', { name: /Abschlag v/ })).toBeTruthy();
		expect(within(table).getByText(new RegExp(m.inbox_processing()))).toBeTruthy();
	});

	it('shows the lanes beyond the limit on demand', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/documents/stream': () => ({
					lanes: [
						series([doc('a', '2026-07-15'), doc('b', '2026-08-15')]),
						series([doc('c', '2026-07-16'), doc('d', '2026-08-16')], { folded: true }),
						{
							...series([doc('e', '2026-08-20')]),
							kind: 'branch',
							parent: 1,
							joins: 'd',
							folded: true
						},
						{ ...series([doc('s', '2026-05-01')]), kind: 'single', number: null }
					],
					truncated: false
				})
			})
		);
		render(StreamView, { props: { query: apiQuery(NO_FILTERS), lookup: null } });
		const table = await screen.findByRole('table', { name: m.stream_lanes() });
		expect(within(table).queryByRole('link', { name: /Abschlag c/ })).toBeNull();
		expect(within(table).getByRole('link', { name: /Abschlag s/ })).toBeTruthy();
		const more = within(table).getByRole('button', {
			name: m.stream_more({ count: formatNumber(2) })
		});
		expect(more.getAttribute('aria-expanded')).toBe('false');
		// A `Button` of the row's size, with its hit area on a phone (WA-12).
		expect(more.getAttribute('data-slot')).toBe('button');
		expect(more.className.split(' ')).toContain('h-8');
		await fireEvent.click(more);
		expect(within(table).getByRole('link', { name: /Abschlag c/ })).toBeTruthy();
		expect(within(table).getByRole('link', { name: /Abschlag e/ })).toBeTruthy();
		// What the branch refers to is read in its row, not only on hover.
		const branch = within(table)
			.getAllByRole('rowheader')
			.find((head) => head.textContent?.includes(m.stream_joins({ title: 'Abschlag d' })));
		expect(branch).toBeTruthy();
		expect(branch?.getAttribute('title')).not.toContain(m.stream_joins({ title: 'Abschlag d' }));
		expect(within(table).getByRole('button', { name: m.stream_fewer() })).toBeTruthy();
	});

	it('stays where one looks when the stream is read again (WA-02)', async () => {
		// Every event of any document reads the stream anew: the lanes folded again and the
		// months jumped back to the newest.
		const lanes = [
			series([doc('a', '2026-07-15'), doc('b', '2026-08-15')]),
			series([doc('c', '2026-07-16'), doc('d', '2026-08-16')], { folded: true })
		];
		const api = fakeApi({
			'GET /api/v1/documents/stream': () => ({ lanes, truncated: false })
		});
		vi.stubGlobal('fetch', api);
		const query = apiQuery(NO_FILTERS);
		const { rerender } = render(StreamView, { props: { query, lookup: null, version: 0 } });
		const table = () => screen.getByRole('table', { name: m.stream_lanes() });
		await screen.findByRole('table', { name: m.stream_lanes() });
		await fireEvent.click(within(table()).getByRole('button', { name: m.stream_more_one() }));
		const scroller = table().closest('.overflow-x-auto')!;
		scroller.scrollLeft = 120;

		await rerender({ query, lookup: null, version: 1 });
		await vi.waitFor(() => expect(calls(api)).toHaveLength(2));
		await settled();
		expect(within(table()).getByRole('link', { name: /Abschlag c/ })).toBeTruthy();
		expect(within(table()).getByRole('button', { name: m.stream_fewer() })).toBeTruthy();
		expect(scroller.scrollLeft).toBe(120);

		// Other filters: a new stream, opened at its newest month, the lanes folded.
		await rerender({
			query: apiQuery({ ...NO_FILTERS, contacts: ['c1'] }),
			lookup: null,
			version: 1
		});
		await vi.waitFor(() => expect(calls(api)).toHaveLength(3));
		await vi.waitFor(() =>
			expect(within(table()).queryByRole('link', { name: /Abschlag c/ })).toBeNull()
		);
		expect(scroller.scrollLeft).toBe(0);
	});

	it('shows a chip in the Beam, paging through its lane: a chip is a small card', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/documents/stream': () => ({
					lanes: [
						series([doc('a', '2026-07-15'), doc('b', '2026-08-15')], {
							target: doc('v', '2026-06-01')
						})
					],
					truncated: false
				})
			})
		);
		render(StreamView, { props: { query: apiQuery(NO_FILTERS), lookup: null } });
		const table = await screen.findByRole('table', { name: m.stream_lanes() });
		const chip = within(table).getByRole('link', { name: /Abschlag b/ });
		expect(chip.getAttribute('aria-haspopup')).toBe('dialog');
		chip.focus();
		await userEvent.keyboard('{Enter}');
		expect(vi.mocked(goto).mock.lastCall?.[1]).toMatchObject({
			shallow: true,
			state: { beam: { ids: ['a', 'b', 'v'], index: 1 } }
		});
	});
});
