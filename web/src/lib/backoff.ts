/** The first wait before the event stream is opened again after the API closed it. */
export const RETRY_FIRST_MS = 5_000;
/** The longest wait: a server that is down keeps being asked once a minute. */
export const RETRY_MAX_MS = 60_000;

/**
 * How long to wait before the next attempt after `failures` attempts in a row failed: doubled
 * each time up to `RETRY_MAX_MS`, and spread by a fifth either way, so that the tabs of every
 * browser do not ask a restarting server at the same moment.
 */
export function retryDelay(failures: number, random: () => number = Math.random): number {
	const base = Math.min(RETRY_MAX_MS, RETRY_FIRST_MS * 2 ** Math.max(0, failures - 1));
	return Math.round(base * (0.8 + 0.4 * random()));
}

/** Where a tab keeps how often it asked a server that cannot be reached: it outlives a reload,
 * which is how the error page asks again. */
const KEPT = 'lekto.retry';
let memory = { failures: 0, at: 0 };

function kept(): { failures: number; at: number } {
	try {
		const found: unknown = JSON.parse(sessionStorage.getItem(KEPT) ?? 'null');
		if (found && typeof found === 'object') {
			const { failures, at } = found as { failures?: unknown; at?: unknown };
			if (typeof failures === 'number' && typeof at === 'number') return { failures, at };
		}
	} catch {
		// No storage (a private window), or not ours: what this page remembers.
	}
	return memory;
}

/**
 * How long to wait before asking a server that cannot be reached again by itself (a page or a
 * card that could not load, web/DESIGN.md "App"): the waits of the event stream, one count for
 * everything in the tab that asks, so that a page of several cards does not ask a restarting
 * server more often than one. The count starts over once nothing had to ask for a while.
 */
export function nextRetry(now: number = Date.now(), random: () => number = Math.random): number {
	const before = kept();
	const failures = now - before.at > 2 * RETRY_MAX_MS ? 1 : before.failures + 1;
	memory = { failures, at: now };
	try {
		sessionStorage.setItem(KEPT, JSON.stringify(memory));
	} catch {
		// Kept in memory then.
	}
	return retryDelay(failures, random);
}

/** Forget the count (for tests). */
export function forgetRetries(): void {
	memory = { failures: 0, at: 0 };
	try {
		sessionStorage.removeItem(KEPT);
	} catch {
		// Nothing was kept.
	}
}
