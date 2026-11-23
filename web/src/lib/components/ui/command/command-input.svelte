<script lang="ts">
	import { Command as CommandPrimitive } from 'bits-ui';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { getContext } from 'svelte';
	import { cn } from '#lib/utils.ts';
	import { COMMAND_LIST } from './command.svelte';

	let {
		ref = $bindable(null),
		class: className,
		value = $bindable(''),
		...restProps
	}: CommandPrimitive.InputProps = $props();

	// The field controls the list of its command.
	const list = getContext<string | undefined>(COMMAND_LIST);
</script>

<div
	class="flex h-9 items-center gap-2 border-b ps-3 pe-8 max-sm:h-12 max-sm:px-4"
	data-slot="command-input-wrapper"
>
	<SearchIcon class="size-4 shrink-0 opacity-50" />
	<CommandPrimitive.Input
		data-slot="command-input"
		class={cn(
			'flex h-10 w-full rounded-md bg-transparent py-3 text-sm outline-hidden placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 max-sm:text-base',
			className
		)}
		bind:ref
		aria-controls={list}
		{...restProps}
		bind:value
	/>
</div>
