<script lang="ts">
	import type { Snippet } from 'svelte';
	import { sideways, SIDEWAYS_FADE } from '#lib/sideways.ts';
	import { cn } from '#lib/utils.ts';

	// A row of small things (badges) that stays one line: where it is wider than the room, it
	// scrolls sideways and the cut edge fades, as `Segmented` and `TabBar` do (web/DESIGN.md,
	// "Tabs and switches"). It never widens the page.
	let {
		label,
		class: className,
		children
	}: { label?: string; class?: string; children: Snippet } = $props();
</script>

<div
	{@attach sideways}
	role={label ? 'group' : undefined}
	aria-label={label}
	class={cn(
		'flex min-w-0 [scrollbar-width:none] items-center gap-1.5 overflow-x-auto whitespace-nowrap',
		SIDEWAYS_FADE,
		className
	)}
>
	{@render children()}
</div>
