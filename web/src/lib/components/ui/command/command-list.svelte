<script lang="ts">
	import { Command as CommandPrimitive } from 'bits-ui';
	import { cn } from '#lib/utils.ts';

	let {
		ref = $bindable(null),
		class: className,
		...restProps
	}: CommandPrimitive.ListProps = $props();
</script>

<CommandPrimitive.List
	bind:ref
	data-slot="command-list"
	class={cn(
		'max-h-[300px] scroll-py-1 overflow-x-hidden overflow-y-auto max-sm:max-h-none max-sm:flex-1 max-sm:overscroll-contain max-sm:px-2 max-sm:pt-2 max-sm:pb-4',
		className
	)}
	{...restProps}
/>
