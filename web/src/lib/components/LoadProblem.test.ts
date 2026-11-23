import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { forgetRetries, RETRY_FIRST_MS } from '#lib/backoff.ts';
import { m } from '#lib/paraglide/messages.js';
import LoadProblem from './LoadProblem.svelte';

beforeEach(() => {
	forgetRetries();
	vi.useFakeTimers();
	vi.spyOn(Math, 'random').mockReturnValue(0.5);
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
});

describe('LoadProblem', () => {
	it('says what went wrong and offers to try again', () => {
		const onretry = vi.fn();
		render(LoadProblem, { problem: 'boom', onretry });
		expect(screen.getByRole('alert').textContent).toContain('boom');
		expect(screen.getByRole('button', { name: m.retry() })).toBeTruthy();
		// Any other problem waits for the person.
		vi.advanceTimersByTime(10 * 60_000);
		expect(onretry).not.toHaveBeenCalled();
		expect(screen.queryByText(m.error_retrying())).toBeNull();
	});

	it('tries again by itself while the server cannot be reached, each time later', () => {
		// Lekto restarts after an update: nobody should have to press "Erneut versuchen".
		const onretry = vi.fn();
		const { unmount } = render(LoadProblem, { problem: m.error_network(), onretry });
		expect(screen.getByText(m.error_retrying())).toBeTruthy();
		vi.advanceTimersByTime(RETRY_FIRST_MS - 1);
		expect(onretry).not.toHaveBeenCalled();
		vi.advanceTimersByTime(1);
		expect(onretry).toHaveBeenCalledTimes(1);
		// Still not there: the second wait is twice the first.
		vi.advanceTimersByTime(2 * RETRY_FIRST_MS - 1);
		expect(onretry).toHaveBeenCalledTimes(1);
		vi.advanceTimersByTime(1);
		expect(onretry).toHaveBeenCalledTimes(2);
		// Loaded, the problem goes: nothing asks any more.
		unmount();
		vi.advanceTimersByTime(10 * 60_000);
		expect(onretry).toHaveBeenCalledTimes(2);
	});

	it('does not try by itself what it cannot try at all', () => {
		render(LoadProblem, { problem: m.error_network() });
		expect(screen.queryByText(m.error_retrying())).toBeNull();
	});
});
