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
