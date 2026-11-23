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
	// `size="sm"` inside a dialog or beside a field (no identifiers yet, nothing assigned);
	// `size="line"` inside a dense card, where the box would outweigh what it stands beside: the
	// words alone, as a line of the card ("Keine Bezüge."). Its `class` takes only what aligns it
	// with the rows around it (their inset, their rule). Further attributes go to the box (a drop
	// target's handlers).
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
		size?: 'md' | 'sm' | 'line';
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
		'text-muted-foreground',
		size === 'line'
			? 'py-2 text-sm'
			: 'flex flex-col items-center rounded-2xl border border-dashed bg-card text-center',
		size === 'sm' && 'gap-3 px-4 py-6 text-sm',
		size === 'md' && cn('gap-4 px-6', compact ? 'py-10' : 'py-16'),
		className
	)}
>
	{#if size !== 'line'}
		{#if mascot}
			<Mascot class="w-16" />
		{:else}
			{@render icon?.()}
		{/if}
	{/if}
	<p>{@render children()}</p>
	{#if size !== 'line'}
		{@render action?.()}
	{/if}
</div>
