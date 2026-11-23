<script lang="ts">
	import { getContext } from 'svelte';
	import { cn, type WithElementRef } from '#lib/utils.ts';
	import type { HTMLAttributes } from 'svelte/elements';
	import { CLOSE_BUTTON } from './dialog-content.svelte';

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> = $props();

	// The X stands in the corner above the head: a long title ends before it.
	const closeButton = getContext<(() => boolean) | undefined>(CLOSE_BUTTON);
</script>

<div
	bind:this={ref}
	data-slot="dialog-header"
	class={cn('flex flex-col gap-2', closeButton?.() && 'pr-8', className)}
	{...restProps}
>
	{@render children?.()}
</div>
