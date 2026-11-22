import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { userEvent } from '@testing-library/user-event';
import { afterEach, describe, expect, it, onTestFinished, vi } from 'vitest';
import { formatNumber } from '#lib/i18n.ts';
import { usageLabel } from '#lib/components/UsageCount.svelte';
import { NODE_LABELS } from '#lib/node-labels.ts';
import { m } from '#lib/paraglide/messages.js';
import { forgetPipeline } from '#lib/pipeline.ts';
import { choose } from '#lib/testing/select.ts';
import { fakeApi } from '#lib/testing/api.ts';
import { BulkRun } from '#lib/bulk.svelte.ts';
import DocumentsBulkBar from './DocumentsBulkBar.svelte';

const node = (name: string, requires: string[] = []) => ({ node: name, requires, waits_for: [] });
const GRAPH = [
	node('receive'),
	node('ocr', ['receive']),
	node('parse', ['ocr']),
	node('signal_llm', ['parse']),
	node('judge', ['signal_llm']),
	node('file', ['judge'])
];

afterEach(() => {
	forgetPipeline();
});

function renderBar(
	count: number,
	merge: { blocked: string | null; start: () => void } | null = null
) {
	const run = new BulkRun(vi.fn());
	// The page stops its run when it is left; here the test ends it. Else an action a test started
	// asks for its state a second later, in whichever test runs then.
	onTestFinished(() => run.stop());
	const rendered = render(DocumentsBulkBar, {
		merge,
		count,
		all: false,
		offerAll: null,
		limit: null,
		capped: null,
		selection: () => ({ ids: ['d1'], query: {} }),
		run,
		lookup: { contacts: [], documentTypes: [], tags: [], fields: [], spaces: [], users: [] },
		onpage: vi.fn(),
		onall: vi.fn(),
		onclear: vi.fn(),
		onend: vi.fn()
	});
	return { ...rendered, run };
}

describe('the selection bar of the documents', () => {
	it('keeps "Details" of what the last action skipped, until the next one (WZ-06)', async () => {
		const { run } = renderBar(0);
		expect(screen.queryByRole('button', { name: m.bulk_details() })).toBeNull();
		const last = {
			id: 'op-1',
			kind: 'confirm',
			status: 'done',
			total: 2,
			done: 2,
			changed: 1,
			unchanged: 0,
			skipped: [{ document_id: 'd2', reason: 'in processing', reasons: [] }],
			error: null,
			created_at: '2026-10-28T12:00:00Z',
			finished_at: '2026-10-28T12:00:05Z'
		} as NonNullable<typeof run.last>;
		run.last = last;
		const details = await screen.findByRole('button', { name: m.bulk_details() });
		expect(screen.getByText(new RegExp(m.bulk_skipped({ count: '1' })))).toBeTruthy();
		await userEvent.click(details);
		expect(run.skipped).toStrictEqual(last);
		run.last = null;
		await waitFor(() =>
			expect(screen.queryByRole('button', { name: m.bulk_details() })).toBeNull()
		);
	});

	it('reprocesses from a chosen step, and says what the model costs for many', async () => {
		const sent: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/pipeline': () => ({ nodes: GRAPH, vision: null }),
				'POST /api/v1/documents/bulk': async (request) => {
					sent.push(await request.json());
					return { id: 'op', status: 'queued', total: 40, done: 0, skipped: [] };
				}
			})
		);
		renderBar(40);
		const more = screen.getByRole('button', { name: m.bulk_more() });
		await fireEvent.pointerDown(more, { button: 0, pointerType: 'mouse' });
		await userEvent.click(await screen.findByRole('menuitem', { name: m.bulk_reprocess() }));
		const dialog = await screen.findByRole('dialog', {
			name: m.bulk_reprocess_title({ documents: usageLabel(40) })
		});
		const warning = m.bulk_reprocess_model({ calls: formatNumber(80) });
		// From the text recognition on, the model is asked too.
		await vi.waitFor(() => expect(dialog.textContent).toContain(warning));
		const step = within(dialog).getByRole('combobox', { name: m.reprocess_from() });
		await vi.waitFor(() => expect(step.textContent).toContain(NODE_LABELS.ocr()));
		await choose(userEvent.setup(), step, 'judge');
		expect(dialog.textContent).not.toContain(warning);
		await userEvent.click(within(dialog).getByRole('button', { name: m.reprocess_title() }));
		await vi.waitFor(() =>
			expect(sent).toEqual([
				{ document_ids: ['d1'], action: { kind: 'reprocess', from_node: 'judge' } }
			])
		);
	});

	it('says nothing of the model for a few documents', async () => {
		vi.stubGlobal(
			'fetch',
			fakeApi({ 'GET /api/v1/pipeline': () => ({ nodes: GRAPH, vision: null }) })
		);
		renderBar(3);
		await fireEvent.pointerDown(screen.getByRole('button', { name: m.bulk_more() }), {
			button: 0,
			pointerType: 'mouse'
		});
		await userEvent.click(await screen.findByRole('menuitem', { name: m.bulk_reprocess() }));
		const dialog = await screen.findByRole('dialog');
		const step = within(dialog).getByRole('combobox', { name: m.reprocess_from() });
		await vi.waitFor(() => expect(step.textContent).toContain(NODE_LABELS.ocr()));
		expect(dialog.textContent).not.toContain(m.bulk_reprocess_model({ calls: '6' }));
	});

	it('merges the chosen documents, or says why not', async () => {
		vi.stubGlobal('fetch', fakeApi({}));
		const start = vi.fn();
		const { rerender } = renderBar(2, { blocked: null, start });
		const more = screen.getByRole('button', { name: m.bulk_more() });
		await fireEvent.pointerDown(more, { button: 0, pointerType: 'mouse' });
		await userEvent.click(await screen.findByRole('menuitem', { name: m.bulk_merge() }));
		expect(start).toHaveBeenCalled();
		await rerender({ merge: { blocked: m.bulk_merge_two(), start } });
		await fireEvent.pointerDown(more, { button: 0, pointerType: 'mouse' });
		const item = await screen.findByRole('menuitem', { name: new RegExp(m.bulk_merge()) });
		expect(item.getAttribute('aria-disabled')).toBe('true');
		expect(item.textContent).toContain(m.bulk_merge_two());
	});
});
