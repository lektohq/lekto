// The error page of the app: a start that failed.
import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { forgetRetries, RETRY_FIRST_MS } from '#lib/backoff.ts';
import { m } from '#lib/paraglide/messages.js';
import Page from './+error.svelte';

const state = vi.hoisted(() => ({ status: 500, error: null as App.Error | null }));
vi.mock('$app/state', () => ({
	page: {
		get status() {
			return state.status;
		},
		get error() {
			return state.error;
		}
	}
}));

const reload = vi.fn();

beforeEach(() => {
	forgetRetries();
	reload.mockReset();
	vi.useFakeTimers();
	vi.spyOn(Math, 'random').mockReturnValue(0.5);
	vi.stubGlobal('location', { ...window.location, reload });
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

describe('the error page', () => {
	it('loads again by itself while the server cannot be reached, and says so', () => {
		state.status = 500;
		state.error = { status: 500, message: m.error_network(), unreachable: true };
		render(Page);
		expect(screen.getByText(m.error_network())).toBeTruthy();
		expect(screen.getByText(m.error_retrying())).toBeTruthy();
		vi.advanceTimersByTime(RETRY_FIRST_MS - 1);
		expect(reload).not.toHaveBeenCalled();
		vi.advanceTimersByTime(1);
		expect(reload).toHaveBeenCalledOnce();
	});

	it('waits for the person after any other error, and on a page that does not exist', () => {
		state.status = 500;
		state.error = { status: 500, message: 'boom' };
		const { unmount } = render(Page);
		vi.advanceTimersByTime(10 * 60_000);
		unmount();
		state.status = 404;
		state.error = { status: 404, message: 'Not Found', unreachable: true };
		render(Page);
		vi.advanceTimersByTime(10 * 60_000);
		expect(reload).not.toHaveBeenCalled();
		expect(screen.queryByText(m.error_retrying())).toBeNull();
	});
});
