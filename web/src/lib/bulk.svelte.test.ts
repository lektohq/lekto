import { afterEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'svelte-sonner';
import { fakeApi, notFound, problem } from '#lib/testing/api.ts';
import { BulkRun, POLL } from './bulk.svelte.ts';

const operation = (status: string, done = 0) => ({
	id: 'op-1',
	kind: 'confirm',
	status,
	total: 2,
	done,
	changed: done,
	unchanged: 0,
	skipped: [],
	error: null,
	created_at: '2026-10-28T12:00:00Z',
	finished_at: null
});

afterEach(() => {
	vi.useRealTimers();
});

describe('an action on many documents, as the page follows it', () => {
	it('polls every second until the action is done, then tells the page', async () => {
		vi.useFakeTimers();
		const answers = [operation('running', 1), operation('done', 2)];
		const polls: string[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/documents/bulk': () => operation('queued'),
				'GET /api/v1/documents/bulk/op-1': (_request, url) => {
					polls.push(url.pathname);
					return answers.shift() ?? operation('done', 2);
				}
			})
		);
		const ondone = vi.fn();
		const run = new BulkRun(ondone);
		await run.start({ ids: ['d1', 'd2'], query: {} }, { kind: 'confirm' });
		expect(run.busy).toBe(true);
		expect(run.operation?.status).toBe('queued');
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.operation?.done).toBe(1);
		expect(ondone).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(POLL);
		expect(polls).toHaveLength(2);
		expect(run.busy).toBe(false);
		expect(ondone).toHaveBeenCalledOnce();
		run.stop();
	});

	it('asks on after a failure that passes, and ends at a refusal (WD-04)', async () => {
		vi.useFakeTimers();
		const failed = vi.spyOn(toast, 'error').mockImplementation(() => '');
		const answers: (() => unknown)[] = [
			() => problem(502),
			() => operation('running', 1),
			// Gone: the API says so every time it is asked.
			() => notFound('bulk operation', 'op-1')
		];
		let polls = 0;
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/documents/bulk': () => operation('queued'),
				'GET /api/v1/documents/bulk/op-1': () => {
					polls += 1;
					return (answers.shift() ?? answers[0])!();
				}
			})
		);
		const ondone = vi.fn();
		const run = new BulkRun(ondone);
		await run.start({ ids: ['d1', 'd2'], query: {} }, { kind: 'confirm' });
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.busy).toBe(true); // the 502 passes
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.operation?.done).toBe(1);
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.busy).toBe(false);
		expect(failed).toHaveBeenCalledOnce();
		expect(ondone).toHaveBeenCalledOnce();
		await vi.advanceTimersByTimeAsync(POLL * 5);
		expect(polls).toBe(3); // not asked for ever
		failed.mockRestore();
	});

	it('keeps the action that skipped documents until the next one starts (WZ-06)', async () => {
		// "Details" stood only in a toast that is gone after four seconds.
		vi.useFakeTimers();
		vi.spyOn(toast, 'warning').mockImplementation(() => '');
		vi.spyOn(toast, 'success').mockImplementation(() => '');
		const skipped = {
			...operation('done', 1),
			skipped: [{ document_id: 'd2', reason: 'in processing', reasons: [] }]
		};
		const answers = [skipped, operation('done', 2)];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/documents/bulk': () => operation('queued'),
				'GET /api/v1/documents/bulk/op-1': () => answers.shift()
			})
		);
		const run = new BulkRun(vi.fn());
		await run.start({ ids: ['d1', 'd2'], query: {} }, { kind: 'confirm' });
		expect(run.last).toBeNull();
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.busy).toBe(false);
		expect(run.last?.skipped).toHaveLength(1);
		// Still there long after the toast went.
		await vi.advanceTimersByTimeAsync(60_000);
		expect(run.last?.skipped).toHaveLength(1);
		// The next action: its own outcome counts.
		await run.start({ ids: ['d1'], query: {} }, { kind: 'confirm' });
		expect(run.last).toBeNull();
		await vi.advanceTimersByTimeAsync(POLL);
		expect(run.last).toBeNull();
		run.stop();
		vi.restoreAllMocks();
	});

	it('changes nothing after it is stopped, even by a poll that was in flight', async () => {
		vi.useFakeTimers();
		let answer: (value: unknown) => void = () => {};
		const polls: string[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'POST /api/v1/documents/bulk': () => operation('queued'),
				'GET /api/v1/documents/bulk/op-1': (_request, url) => {
					polls.push(url.pathname);
					return new Promise((resolve) => (answer = resolve));
				}
			})
		);
		const ondone = vi.fn();
		const run = new BulkRun(ondone);
		await run.start({ ids: ['d1'], query: {} }, { kind: 'confirm' });
		await vi.advanceTimersByTimeAsync(POLL);
		expect(polls).toHaveLength(1);
		// The page is left while the answer is on its way.
		run.stop();
		answer(operation('done', 1));
		await vi.advanceTimersByTimeAsync(POLL * 3);
		expect(polls).toHaveLength(1);
		expect(run.operation?.status).toBe('queued');
		expect(ondone).not.toHaveBeenCalled();
	});
});
