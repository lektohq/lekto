<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cn } from '#lib/utils.ts';

	// A row of small things (badges) that stays one line: where it is wider than the room, it
	// scrolls sideways and the cut edge fades, as `Segmented` and `TabBar` do (web/DESIGN.md,
	// "Tabs and switches"). It never widens the page.
	let {
		label,
		class: className,
		children
	}: { label?: string; class?: string; children: Snippet } = $props();

	let room = $state<HTMLElement | null>(null);
	/** Which edges have more behind them. */
	let more = $state<{ start: boolean; end: boolean }>({ start: false, end: false });

	function measure() {
		if (!room) return;
		const end = room.scrollWidth - room.clientWidth - room.scrollLeft;
		more = { start: room.scrollLeft > 1, end: end > 1 };
	}

	$effect(() => {
		if (!room) return;
		const sizes = new ResizeObserver(measure);
		sizes.observe(room);
		for (const child of room.children) sizes.observe(child);
		return () => sizes.disconnect();
	});
</script>

<div
	bind:this={room}
	onscroll={measure}
	role={label ? 'group' : undefined}
	aria-label={label}
	data-more-start={more.start || undefined}
	data-more-end={more.end || undefined}
	class={cn(
		'flex min-w-0 [scrollbar-width:none] items-center gap-1.5 overflow-x-auto whitespace-nowrap',
		'data-more-end:[mask-image:linear-gradient(to_right,black_85%,transparent)]',
		'data-more-start:[mask-image:linear-gradient(to_left,black_85%,transparent)]',
		'data-more-start:data-more-end:[mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]',
		className
	)}
>
	{@render children()}
</div>
