/**
 * The history entry a navigation of the app was about to make, for a guard that holds the
 * navigation back and lets it go on later (`UnsavedGuard`, "Verwerfen"): SvelteKit tells a guard
 * where a navigation leads, not the state it carries. Without it the words of a search would be
 * lost on the way (`lib/words.ts`: they stand in the entry, never in the address).
 */
import { goto } from '$app/navigation';

let last: { href: string; state: App.PageState } | null = null;

function absolute(url: string | URL): string {
	return new URL(url, window.location.href).href;
}

/** Go to `url` with `state` in its history entry, kept over a reload. */
export function gotoWithState(
	url: string | URL,
	state: App.PageState,
	options: { replace?: boolean; reset?: boolean } = {}
): Promise<void> {
	last = { href: absolute(url), state };
	return goto(url, { ...options, state, persistState: true });
}

/** The state the last such navigation to `url` carried, if it led there. */
export function heldState(url: URL): App.PageState | undefined {
	return last && last.href === url.href ? last.state : undefined;
}
