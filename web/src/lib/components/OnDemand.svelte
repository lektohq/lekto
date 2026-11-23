<script lang="ts">
	import { onMount, type Component } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { m } from '#lib/paraglide/messages.js';

	// A part every page may open but few do (the Beam, the dialogs of the master data): its
	// code is loaded when it is first wanted, not with every page before its first picture.
	// Once the page stands and the browser is idle it is loaded ahead, so that the first
	// opening does not wait. A tab from before an update no longer finds the file of a part it
	// never loaded: it says so, and a reload brings the new app.
	let {
		load,
		wanted
	}: {
		/** The import of the part (`() => import('…svelte')`). */
		load: () => Promise<{ default: Component }>;
		/** Something asks for the part now. */
		wanted: boolean;
	} = $props();

	/** How long the page may stand before the part is loaded ahead without an idle moment. */
	const AHEAD_MS = 3000;

	let Part = $state<Component | null>(null);
	let pending: Promise<void> | null = null;

	function fetch() {
		pending ??= load().then(
			(module) => {
				Part = module.default;
			},
			() => {
				pending = null;
				if (wanted) toast.error(m.part_load_failed());
			}
		);
	}

	$effect(() => {
		if (wanted && !Part) fetch();
	});

	onMount(() => {
		if ('requestIdleCallback' in window) {
			const idle = window.requestIdleCallback(fetch, { timeout: AHEAD_MS });
			return () => window.cancelIdleCallback(idle);
		}
		const timer = setTimeout(fetch, AHEAD_MS);
		return () => clearTimeout(timer);
	});
</script>

{#if Part}<Part />{/if}
