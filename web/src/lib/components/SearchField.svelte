<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLInputAttributes } from 'svelte/elements';
	import SearchIcon from '@lucide/svelte/icons/search';
	import { FIELD_FRAME, FIELD_HEIGHT } from '#lib/components/ui/field-look.ts';
	import { cn } from '#lib/utils.ts';

	// Every search field (web/DESIGN.md, "Fields"): a magnifier, then the input, in the frame of
	// the fields. `md` is as high as every field (`FIELD_HEIGHT`) and stands in pages, the header,
	// pickers and dialogs; `sm` is the 36 px of the narrow filter panel. `class` sets the width;
	// `label` names the input and prompts it unless `placeholder` says more. `end` stands after the
	// input (a key hint, a button that clears); further attributes go to the input.
	let {
		value = $bindable(''),
		label,
		placeholder,
		size = 'md',
		class: className,
		ref = $bindable(null),
		end,
		...rest
	}: Omit<HTMLInputAttributes, 'value' | 'size' | 'class' | 'type' | 'placeholder'> & {
		value?: string;
		label: string;
		placeholder?: string;
		size?: 'sm' | 'md';
		class?: string;
		/** The input, for the focus. */
		ref?: HTMLInputElement | null;
		end?: Snippet;
	} = $props();
</script>

<label
	class={cn(
		FIELD_FRAME,
		size === 'sm' ? 'h-9 gap-1.5 px-2.5' : cn(FIELD_HEIGHT, 'px-3.5', end && 'pr-1.5'),
		className
	)}
>
	<SearchIcon class={cn('shrink-0', size === 'sm' ? 'size-3.5' : 'size-4')} aria-hidden="true" />
	<input
		{...rest}
		bind:this={ref}
		bind:value
		type="search"
		aria-label={label}
		placeholder={placeholder ?? label}
		class="h-full min-w-0 flex-1 bg-transparent text-base text-foreground outline-none placeholder:text-muted-foreground sm:text-sm [&::-webkit-search-cancel-button]:hidden"
	/>
	{@render end?.()}
</label>
