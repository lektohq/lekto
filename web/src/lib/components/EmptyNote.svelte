<script lang="ts">
	import type { Snippet } from 'svelte';
	import Mascot from '#lib/components/Mascot.svelte';
	import { cn } from '#lib/utils.ts';

	// A list with nothing in it: a dashed box with the words for it, as every page shows it, and
	// where there is one the way to what would fill it (`action`; web/DESIGN.md, "States").
	// `mascot` puts the owl above the words, only where nothing is a moment of its own
	// ("Logo and owl"): the inbox with nothing waiting, the documents before the first one. `icon`
	// stands there instead where the box says what a gesture does (dropping files on the inbox).
	let {
		compact = false,
		mascot = false,
		class: className,
		icon,
		action,
		children
	}: {
		compact?: boolean;
		mascot?: boolean;
		class?: string;
		icon?: Snippet;
		action?: Snippet;
		children: Snippet;
	} = $props();
</script>

<div
	class={cn(
		'flex flex-col items-center gap-4 rounded-2xl border border-dashed bg-card px-6 text-center text-muted-foreground',
		compact ? 'py-10' : 'py-16',
		className
	)}
>
	{#if mascot}
		<Mascot class="w-16" />
	{:else}
		{@render icon?.()}
	{/if}
	<p>{@render children()}</p>
	{@render action?.()}
</div>
