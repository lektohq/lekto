<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import Mascot from '#lib/components/Mascot.svelte';
	import { cn } from '#lib/utils.ts';

	// A list with nothing in it: a dashed box with the words for it, as every page shows it, and
	// where there is one the way to what would fill it (`action`; web/DESIGN.md, "States").
	// `mascot` puts the owl above the words, only where nothing is a moment of its own
	// ("Logo and owl"): the inbox with nothing waiting, the documents before the first one. `icon`
	// stands there instead where the box says what a gesture does (dropping files on the inbox).
	// `size="sm"` inside a dialog or beside a field (no identifiers yet, nothing assigned); further
	// attributes go to the box (a drop target's handlers).
	let {
		compact = false,
		size = 'md',
		mascot = false,
		class: className,
		icon,
		action,
		children,
		...rest
	}: Omit<HTMLAttributes<HTMLDivElement>, 'children'> & {
		compact?: boolean;
		size?: 'md' | 'sm';
		mascot?: boolean;
		class?: string;
		icon?: Snippet;
		action?: Snippet;
		children: Snippet;
	} = $props();
</script>

<div
	{...rest}
	class={cn(
		'flex flex-col items-center rounded-2xl border border-dashed bg-card text-center text-muted-foreground',
		size === 'sm' ? 'gap-3 px-4 py-6 text-sm' : cn('gap-4 px-6', compact ? 'py-10' : 'py-16'),
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
