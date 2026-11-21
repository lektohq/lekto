import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HIDDEN_GRACE_MS, whileVisible } from './visible.ts';

let state: DocumentVisibilityState = 'visible';
const show = (next: DocumentVisibilityState) => {
	state = next;
	document.dispatchEvent(new Event('visibilitychange'));
};

beforeEach(() => {
	state = 'visible';
	vi.useFakeTimers();
	vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => state);
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
});

describe('what a tab holds only while it is looked at (WP-02)', () => {
	it('lets go once the tab was hidden for a while, and takes it up again when shown', () => {
		const open = vi.fn();
		const close = vi.fn();
		const end = whileVisible(open, close);
		expect(open).toHaveBeenCalledTimes(1);

		show('hidden');
		vi.advanceTimersByTime(HIDDEN_GRACE_MS - 1);
		expect(close).not.toHaveBeenCalled();
		vi.advanceTimersByTime(1);
		expect(close).toHaveBeenCalledTimes(1);

		show('visible');
		expect(open).toHaveBeenCalledTimes(2);
		end();
		show('hidden');
		vi.advanceTimersByTime(HIDDEN_GRACE_MS * 2);
		expect(close).toHaveBeenCalledTimes(1);
	});

	it('keeps what it holds over a look at another tab and back', () => {
		const open = vi.fn();
		const close = vi.fn();
		whileVisible(open, close);
		show('hidden');
		vi.advanceTimersByTime(HIDDEN_GRACE_MS - 1);
		show('visible');
		vi.advanceTimersByTime(HIDDEN_GRACE_MS * 2);
		expect([open.mock.calls.length, close.mock.calls.length]).toEqual([1, 0]);
	});

	it('takes nothing up in a tab opened in the background, until it is shown', () => {
		state = 'hidden';
		const open = vi.fn();
		whileVisible(open, vi.fn());
		expect(open).not.toHaveBeenCalled();
		show('visible');
		expect(open).toHaveBeenCalledTimes(1);
	});
});
