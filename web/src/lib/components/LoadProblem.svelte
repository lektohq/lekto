<script lang="ts">
	import WifiOff from '@lucide/svelte/icons/wifi-off';
	import type { Snippet } from 'svelte';
	import { online } from 'svelte/reactivity/window';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A page or panel could not load: what went wrong, and a way to try again. `children` are
	// further actions beside the retry button. Without a connection it says so instead and tries
	// again by itself once the device is back online (web/DESIGN.md, "App").
	let {
		problem,
		onretry,
		children
	}: { problem: string; onretry?: () => void; children?: Snippet } = $props();

	const offline = $derived(online.current === false);
	let wasOffline = false;
	$effect(() => {
		if (offline) {
			wasOffline = true;
		} else if (wasOffline) {
			wasOffline = false;
			onretry?.();
		}
	});
</script>

<div class="flex flex-col items-start gap-3" role="alert">
	{#if offline}
		<p class="flex items-center gap-2 text-muted-foreground">
			<WifiOff class="size-4 shrink-0" aria-hidden="true" />{m.offline_problem()}
		</p>
	{:else}
		<p class="text-destructive">{problem}</p>
	{/if}
	{#if onretry || children}
		<div class="flex flex-wrap gap-2">
			{#if onretry}
				<Button variant="outline" onclick={onretry}>{m.retry()}</Button>
			{/if}
			{@render children?.()}
		</div>
	{/if}
</div>
