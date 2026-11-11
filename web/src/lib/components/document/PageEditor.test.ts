import { fireEvent, render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { showPages } from '#lib/beam.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
import PageEditor from './PageEditor.svelte';

// The Beam is the app's: here only what the editor hands it.
vi.mock('#lib/beam.svelte.ts', async (original) => ({
	...(await original<typeof import('#lib/beam.svelte.ts')>()),
	showPages: vi.fn()
}));

type Document = components['schemas']['DocumentDetails'];

const DOCUMENT = { id: 'doc-1', title: '2022/11', page_count: 3 } as unknown as Document;

let sent: FormData | null = null;
let fetchMock = fakeApi();

beforeEach(() => {
	sent = null;
	fetchMock = fakeApi({
		'POST /api/v1/documents/doc-1/edit/pages': () => ({
			pages: ['data:image/webp;base64,AA==', 'data:image/webp;base64,AQ==']
		}),
		'POST /api/v1/documents/doc-1/edit': async (request) => {
			sent = await request.formData();
			return { documents: [], deleted: false };
		}
	});
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => vi.unstubAllGlobals());

function open(onedited = vi.fn()) {
	render(PageEditor, { open: true, document: DOCUMENT, onedited });
	return onedited;
}

const page = (number: number) =>
	screen.getByRole('checkbox', { name: m.page_edit_page({ page: String(number) }) });
const parts = () => JSON.parse(String(sent?.get('parts')));

describe('PageEditor', () => {
	it('shows the pages and has nothing to apply as they came', () => {
		open();
		expect(screen.getAllByRole('checkbox')).toHaveLength(3);
		expect(screen.getByRole('button', { name: m.page_edit_next() })).toHaveProperty(
			'disabled',
			true
		);
	});

	it('turns, cuts, and lets the chosen part replace the document', async () => {
		const user = userEvent.setup();
		const onedited = open();
		await user.click(page(3));
		const bar = screen.getByRole('region', { name: m.page_edit_chosen_one() });
		await user.click(within(bar).getByRole('button', { name: m.page_edit_left_short() }));
		await user.click(screen.getByRole('button', { name: m.page_cut_after({ page: '1' }) }));
		expect(
			screen.getByText(
				`${m.page_edit_part({ number: '2' })} · ${m.page_edit_part_pages({ first: '2', last: '3' })}`
			)
		).toBeTruthy();
		await user.click(screen.getByRole('button', { name: m.page_edit_next_parts({ count: 2 }) }));
		// The first part replaces it at first; the second takes over.
		const replaces = screen.getAllByRole('button', {
			name: m.page_edit_version()
		});
		await user.click(replaces[1]);
		expect(
			screen.getByText(m.page_edit_kept_any({ title: '2022/11', part: '2' }), { exact: false })
		).toBeTruthy();
		await user.click(screen.getByRole('button', { name: m.page_edit_apply() }));
		expect(parts()).toEqual([
			{ pages: [{ source: 0, page: 1, rotate: 0 }], replaces: false },
			{
				pages: [
					{ source: 0, page: 2, rotate: 0 },
					{ source: 0, page: 3, rotate: 270 }
				],
				replaces: true
			}
		]);
		expect(onedited).toHaveBeenCalled();
	});

	it('chooses all pages or none from "Auswählen", the tools staying where they are', async () => {
		const user = userEvent.setup();
		open();
		const bar = () => screen.getByRole('region', { name: /selected|gewählt/ });
		const tools = () =>
			within(bar())
				.getAllByRole('button')
				.map((button) => button.textContent?.trim());
		const before = tools();
		const choose = async (item: string) => {
			const chooser = within(bar()).getByRole('button', { name: m.bulk_mode() });
			await fireEvent.pointerDown(chooser, { button: 0, pointerType: 'mouse' });
			await user.click(await screen.findByRole('menuitem', { name: item }));
		};
		await choose(m.page_edit_select_all());
		expect(screen.getByRole('region', { name: m.page_edit_chosen({ count: 3 }) })).toBeTruthy();
		expect(tools()).toEqual(before);
		await choose(m.bulk_select_none());
		expect(screen.getByRole('region', { name: m.page_edit_none() })).toBeTruthy();
	});

	it('shows a page in the Beam among the parts as they are to be, by its eye or B', async () => {
		const user = userEvent.setup();
		open();
		await user.click(page(3));
		const bar = screen.getByRole('region', { name: m.page_edit_chosen_one() });
		await user.click(within(bar).getByRole('button', { name: m.page_edit_right_short() }));
		await user.click(screen.getByRole('button', { name: m.page_cut_after({ page: '1' }) }));
		await user.click(
			screen.getByRole('button', {
				name: m.beam_open_named({ title: m.page_edit_page({ page: '3' }) })
			})
		);
		const [parts, index, , start] = vi.mocked(showPages).mock.lastCall!;
		expect(parts.map((part) => [part.title, part.meta])).toEqual([
			[m.page_edit_part({ number: '1' }), m.page_edit_part_page({ page: '1' })],
			[m.page_edit_part({ number: '2' }), m.page_edit_part_pages({ first: '2', last: '3' })]
		]);
		expect(parts[1].pages.map((shown) => shown.turn)).toEqual([0, 90]);
		expect([index, start]).toEqual([1, 2]);
		page(1).focus();
		await user.keyboard('b');
		expect(vi.mocked(showPages).mock.lastCall?.slice(1, 2)).toEqual([0]);
		expect(vi.mocked(showPages).mock.lastCall?.[3]).toBe(1);
	});

	it('deletes the document where no part replaces it, and says so first', async () => {
		const user = userEvent.setup();
		open();
		await user.click(screen.getByRole('button', { name: m.page_cut_after({ page: '2' }) }));
		await user.click(screen.getByRole('button', { name: m.page_edit_next_parts({ count: 2 }) }));
		await user.click(screen.getAllByRole('button', { name: m.page_edit_new() })[0]);
		expect(
			screen.getByText(m.page_edit_deleted({ title: '2022/11' }), { exact: false })
		).toBeTruthy();
		// Back to the pages and on again keeps the stack.
		await user.click(screen.getByRole('button', { name: m.editor_back() }));
		expect(screen.getAllByRole('checkbox')).toHaveLength(3);
		await user.click(screen.getByRole('button', { name: m.page_edit_next_parts({ count: 2 }) }));
		await user.click(screen.getByRole('button', { name: m.page_edit_apply() }));
		expect(parts().map((part: { replaces: boolean }) => part.replaces)).toEqual([false, false]);
	});

	it('moves a page with Ctrl and an arrow, and undoes it', async () => {
		const user = userEvent.setup();
		open();
		page(1).focus();
		await user.keyboard('{Control>}{ArrowRight}{/Control}');
		const names = () =>
			screen
				.getAllByRole('checkbox')
				.map((box) => box.closest('label')?.querySelector('img')?.getAttribute('src'));
		expect(names()[1]).toContain('/pages/1');
		await user.click(screen.getByRole('button', { name: m.page_edit_undo() }));
		expect(names()[0]).toContain('/pages/1');
	});

	it('adds the pages of a file after the chosen page and sends the file along', async () => {
		// A form with a file of the test's DOM reaches the fake API unreadable: what goes into it
		// is checked instead.
		const appended = vi.spyOn(FormData.prototype, 'append');
		const user = userEvent.setup();
		open();
		await user.click(page(1));
		const picker = document.body.querySelector<HTMLInputElement>('input[type=file]');
		const file = new File(['%PDF-1.7'], 'forgotten.pdf', { type: 'application/pdf' });
		await user.upload(picker!, file);
		expect(await screen.findAllByRole('checkbox')).toHaveLength(5);
		await user.click(screen.getByRole('button', { name: m.page_edit_next() }));
		await user.click(screen.getByRole('button', { name: m.page_edit_apply() }));
		const fields = appended.mock.calls.filter(([name]) => name !== 'file');
		const [, text] = fields.find(([name]) => name === 'parts')!;
		const picks = JSON.parse(String(text))[0].pages.map(
			(pick: { source: number; page: number }) => `${pick.source}:${pick.page}`
		);
		expect(picks).toEqual(['0:1', '1:1', '1:2', '0:2', '0:3']);
		expect(fields.find(([name]) => name === 'files')?.[1]).toBe(file);
		appended.mockRestore();
	});

	it('merges documents: marks their pages, needs a part for the target, sends the documents', async () => {
		const user = userEvent.setup();
		const scan = { id: 'doc-2', title: 'scan_0412', page_count: 2 };
		const onedited = vi.fn();
		render(PageEditor, { open: true, document: DOCUMENT, mergeWith: [scan], onedited });
		expect(screen.getByText(m.merge_title({ count: '2' }))).toBeTruthy();
		expect(screen.getByText(m.page_edit_source({ mark: 'B', title: 'scan_0412' }))).toBeTruthy();
		const from = screen.getByRole('checkbox', {
			name: m.page_edit_page_from({ page: '4', title: 'scan_0412' })
		});
		expect(from.closest('label')?.textContent).toContain('B');
		// The scan's first page goes (its blank back, say).
		await user.click(from);
		await user.click(
			within(screen.getByRole('region', { name: m.page_edit_chosen_one() })).getByRole('button', {
				name: m.page_edit_remove()
			})
		);
		await user.click(screen.getByRole('button', { name: m.page_edit_next() }));
		// Without a part that continues a document, nothing is merged.
		await user.click(screen.getByRole('button', { name: m.page_edit_new() }));
		expect(screen.getByText(m.merge_needs_target())).toBeTruthy();
		expect(screen.getByRole('button', { name: m.page_edit_apply() })).toHaveProperty(
			'disabled',
			true
		);
		await user.click(screen.getByRole('button', { name: m.page_edit_version() }));
		expect(
			screen.getByText(m.merge_gone_one({ title: 'scan_0412', target: '2022/11' }), {
				exact: false
			})
		).toBeTruthy();
		await user.click(screen.getByRole('button', { name: m.page_edit_apply() }));
		expect(parts()).toEqual([
			{
				pages: [
					{ source: 0, page: 1, rotate: 0 },
					{ source: 0, page: 2, rotate: 0 },
					{ source: 0, page: 3, rotate: 0 },
					{ source: 1, page: 2, rotate: 0 }
				],
				replaces: true
			}
		]);
		expect(JSON.parse(String(sent?.get('documents')))).toEqual(['doc-2']);
		expect(sent?.get('target')).toBeNull();
		expect(onedited).toHaveBeenCalledWith(expect.anything(), 'doc-1');
	});

	it('merges no document whose pages all left the stack', async () => {
		const user = userEvent.setup();
		const scan = { id: 'doc-2', title: 'scan_0412', page_count: 2 };
		render(PageEditor, { open: true, document: DOCUMENT, mergeWith: [scan], onedited: vi.fn() });
		for (const number of [4, 5]) {
			await user.click(
				screen.getByRole('checkbox', {
					name: m.page_edit_page_from({ page: '4', title: 'scan_0412' })
				})
			);
			await user.click(
				within(screen.getByRole('region', { name: m.page_edit_chosen_one() })).getByRole('button', {
					name: m.page_edit_remove()
				})
			);
			expect(screen.getAllByRole('checkbox')).toHaveLength(8 - number);
		}
		expect(screen.getByText(m.page_edit_title({ title: '2022/11' }))).toBeTruthy();
		expect(screen.queryByText(m.page_edit_source({ mark: 'B', title: 'scan_0412' }))).toBeNull();
		// The document's own pages as they came: nothing to apply, nothing merged.
		expect(screen.getByRole('button', { name: m.page_edit_next() })).toHaveProperty(
			'disabled',
			true
		);
	});
});
