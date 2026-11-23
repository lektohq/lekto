<script lang="ts">
	import WifiOff from '@lucide/svelte/icons/wifi-off';
	import type { Snippet } from 'svelte';
	import { online } from 'svelte/reactivity/window';
	import { nextRetry } from '#lib/backoff.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { saysUnreachable } from '#lib/errors.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A page or panel could not load: what went wrong, and a way to try again. `children` are
	// further actions beside the retry button. Without a connection it says so instead and tries
	// again by itself once the device is back online (web/DESIGN.md, "App"). Where the server
	// cannot be reached (it restarts after an update) it tries again by itself too, with the
	// growing waits of the event stream (`nextRetry`), and says so.
	let {
		problem,
		onretry,
		children
	}: { problem: string; onretry?: () => void; children?: Snippet } = $props();

	const offline = $derived(online.current === false);
	const retrying = $derived(!offline && onretry !== undefined && saysUnreachable(problem));
	$effect(() => {
		if (!retrying) return;
		let timer: ReturnType<typeof setTimeout>;
		const wait = () => {
			timer = setTimeout(() => {
				onretry?.();
				// Still here after the attempt: the next one waits longer.
				wait();
			}, nextRetry());
		};
		wait();
		return () => clearTimeout(timer);
	});
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
		{#if retrying}<p class="text-sm text-muted-foreground">{m.error_retrying()}</p>{/if}
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
