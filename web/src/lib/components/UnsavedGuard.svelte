<script lang="ts">
	import { afterNavigate, beforeNavigate, goto } from '$app/navigation';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import { gotoWithState, heldState } from '#lib/held-state.ts';
	import { m } from '#lib/paraglide/messages.js';

	// Asks before changes are lost (web/DESIGN.md, "Saving and leaving"): while `dirty`, leaving
	// the page by a link, a tab, the back button or closing the window asks first; "Discard"
	// goes on, anything else stays. The form clears `dirty` once it saved or the person cancelled.
	// `keeps`: a move within the page that keeps the form (a pane shown instead of another) asks
	// nothing. "Discard" goes on the way the person went: back or forward in the history where the
	// browser's buttons led (no new entry, which a second "back" would return from into the
	// discarded form), else to the address with the state the navigation carried (the words of a
	// search, `lib/held-state.ts`).
	let { dirty, keeps }: { dirty: boolean; keeps?: (from: URL, to: URL) => boolean } = $props();

	let asking = $state(false);
	let target = $state<URL | null>(null);
	// How far the browser's back or forward button went; null for a link or a `goto`.
	let delta: number | null = null;
	let leaving = false;

	beforeNavigate((navigation) => {
		if (!dirty || leaving) return;
		// Closing the window or leaving the app: only the browser's own question is possible.
		if (navigation.type === 'leave') {
			navigation.cancel();
			return;
		}
		if (!navigation.to) return;
		if (navigation.from && keeps?.(navigation.from.url, navigation.to.url)) return;
		navigation.cancel();
		target = navigation.to.url;
		delta = navigation.type === 'popstate' ? navigation.delta : null;
		asking = true;
	});

	// The navigation "Discard" let go on has arrived (or another one has): guard again.
	afterNavigate(() => {
		leaving = false;
	});

	async function discard() {
		if (!target) return;
		leaving = true;
		asking = false;
		if (delta !== null) {
			// SvelteKit went back to this entry when the navigation was cancelled: go again.
			history.go(delta);
			return;
		}
		const state = heldState(target);
		await (state ? gotoWithState(target, state) : goto(target));
		leaving = false;
	}
</script>

<ConfirmDialog
	bind:open={asking}
	title={m.unsaved_title()}
	description={m.unsaved_hint()}
	confirmLabel={m.unsaved_discard()}
	onconfirm={discard}
/>
