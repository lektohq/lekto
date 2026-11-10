<script lang="ts">
	import Scissors from '@lucide/svelte/icons/scissors';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { cn } from '#lib/utils.ts';

	// The gap between two pages of a stack (web/DESIGN.md, "Page cut"): a toggle "Nach Seite n
	// trennen", 24 px wide (44 px on a phone). Set, a line in `primary` with the scissors; unset,
	// the scissors faintly (nothing depends on hover), the line under the pointer. `target`: a page being moved would
	// land here. The keyboard cuts with Enter on a page (the grid), so the gap is no tab stop.
	let {
		after,
		cut,
		target = false,
		ontoggle
	}: {
		/** The place of the page before the gap. */
		after: number;
		cut: boolean;
		target?: boolean;
		ontoggle: () => void;
	} = $props();
</script>

<button
	type="button"
	tabindex="-1"
	aria-pressed={cut}
	aria-label={m.page_cut_after({ page: String(after) })}
	class={cn(
		'group relative flex shrink-0 cursor-pointer items-center justify-center self-stretch',
		phone.current ? 'w-11' : 'w-6'
	)}
	onclick={ontoggle}
>
	<span
		aria-hidden="true"
		class={cn(
			'absolute inset-y-2 left-1/2 w-0.5 -translate-x-1/2 rounded-full',
			cut || target ? 'bg-primary' : 'bg-transparent group-hover:bg-border'
		)}
	></span>
	<span
		aria-hidden="true"
		class={cn(
			'relative grid size-6 place-items-center rounded-full',
			cut
				? 'bg-primary text-primary-foreground'
				: 'text-muted-foreground/50 group-hover:bg-card group-hover:text-muted-foreground'
		)}
	>
		<Scissors class="size-3.5" />
	</span>
</button>
