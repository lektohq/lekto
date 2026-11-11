<script lang="ts">
	import { cn, type WithElementRef } from '#lib/utils.ts';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		inset,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> & {
		inset?: boolean;
	} = $props();
</script>

<div
	bind:this={ref}
	data-slot="dropdown-menu-label"
	data-inset={inset}
	class={cn(
		'px-1.5 py-1 text-xs font-medium text-muted-foreground data-inset:pl-7 max-sm:px-3 max-sm:pt-2 max-sm:text-sm',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</div>
