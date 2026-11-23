<script lang="ts">
	import { Command as CommandPrimitive } from 'bits-ui';
	import { getContext } from 'svelte';
	import { cn } from '#lib/utils.ts';
	import { COMMAND_LIST } from './command.svelte';

	let {
		ref = $bindable(null),
		class: className,
		'aria-label': label,
		...restProps
	}: Omit<CommandPrimitive.ListProps, 'aria-label'> & {
		/** What the list offers, as its picker is titled: bits-ui calls it "Suggestions..."
		 * otherwise, whatever the language. */
		'aria-label': string;
	} = $props();

	// The search field controls it by this id.
	const list = getContext<string | undefined>(COMMAND_LIST);
</script>

<CommandPrimitive.List
	bind:ref
	id={list}
	aria-label={label}
	data-slot="command-list"
	class={cn(
		'max-h-[300px] scroll-py-1 overflow-x-hidden overflow-y-auto max-sm:max-h-none max-sm:flex-1 max-sm:overscroll-contain max-sm:px-2 max-sm:pt-2 max-sm:pb-4',
		className
	)}
	{...restProps}
/>
