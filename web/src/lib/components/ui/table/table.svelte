<script lang="ts">
	import { cn, type WithElementRef } from '#lib/utils.ts';
	import type { HTMLTableAttributes } from 'svelte/elements';

	// A table in a container that scrolls sideways where the table is wider. While it does, the
	// container is a region with a name that the keyboard reaches (`label`; web/DESIGN.md,
	// "Tables"): else a table without anything to focus in it keeps its right columns from who
	// does not use a pointer, and a screen reader lands on a scroller without a name.
	let {
		ref = $bindable(null),
		class: className,
		label,
		children,
		...restProps
	}: WithElementRef<HTMLTableAttributes> & {
		/** What the table holds ("Jobs"): the name of the region while it scrolls. */
		label: string;
	} = $props();

	let container = $state<HTMLElement | null>(null);
	let scrolls = $state(false);

	$effect(() => {
		if (!container) return;
		const room = container;
		const measure = () => (scrolls = room.scrollWidth > room.clientWidth + 1);
		const sizes = new ResizeObserver(measure);
		sizes.observe(room);
		if (ref) sizes.observe(ref);
		measure();
		return () => sizes.disconnect();
	});
</script>

<!-- Focusable only while it scrolls, as a scroller is; then it is no static element. -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
	bind:this={container}
	data-slot="table-container"
	class="relative w-full overflow-x-auto"
	role={scrolls ? 'region' : undefined}
	aria-label={scrolls ? label : undefined}
	tabindex={scrolls ? 0 : undefined}
>
	<table
		bind:this={ref}
		data-slot="table"
		class={cn('w-full caption-bottom text-sm', className)}
		{...restProps}
	>
		{@render children?.()}
	</table>
</div>
