<script lang="ts" module>
	/** Where the bar of a desktop sticks: below the header (64 px), with room (`top-20`). */
	export const SELECTION_TOP = 80;
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { cardVariants } from '#lib/components/ui/card/index.ts';
	import { phone } from '#lib/phone.svelte.ts';
	import { cn } from '#lib/utils.ts';

	// The bar of a list whose items are chosen many at once (web/DESIGN.md, "Choosing many"):
	// what stands before the count (`lead`: an X, a chooser), how many are chosen (`count`, also
	// the bar's name), a hint in words (`hint`: how far the choice reaches, what an action leaves
	// out), what stands between them and the actions (`trail`: "Auswahl aufheben", a chooser) and
	// the actions. On a desktop it stands above the list with the card look in `bg-panel` and
	// sticks below the header (64 px tall: `top-20`, `SELECTION_TOP`), above a sticky band. In a dialog (`inDialog`) it stands in a
	// fixed part of the dialog, which does not scroll: above the body, on a phone below it. On a
	// phone it sticks to the bottom of the screen in `bg-card` with a line above: `trail` follows
	// the count, the hint is a line of its own and the actions share the width.
	let {
		count,
		busy = false,
		lead,
		trail,
		hint,
		actions,
		inDialog = false,
		height = $bindable(0)
	}: {
		/** How many are chosen, in words ("3 ausgewählt"). */
		count: string;
		/** An action runs on the choice. */
		busy?: boolean;
		lead?: Snippet;
		trail?: Snippet;
		hint?: Snippet;
		actions?: Snippet;
		/** It stands in the scrolling body of a dialog, not on a page. */
		inDialog?: boolean;
		/** Its height as it stands, for what sticks below it (web/DESIGN.md, "Sticky heads"). */
		height?: number;
	} = $props();
</script>

<div
	class={cn(
		'flex flex-wrap items-center gap-x-3 gap-y-2',
		phone.current
			? cn(
					'border-t bg-card px-4 pt-2 pb-[max(1rem,calc(env(safe-area-inset-bottom)+0.5rem))]',
					!inDialog && 'sticky bottom-0 z-10 -mx-4'
				)
			: cn(
					cardVariants({ size: 'flush' }),
					'bg-panel py-1.5 pr-2',
					!inDialog && 'sticky top-20 z-30',
					lead ? 'pl-1.5' : 'pl-4'
				)
	)}
	role="region"
	aria-label={count}
	aria-busy={busy || undefined}
	bind:offsetHeight={height}
>
	{@render lead?.()}
	<span class={cn('font-medium', phone.current && 'flex-1')}>{count}</span>
	{#if phone.current}{@render trail?.()}{/if}
	{#if hint}
		<span class={cn('text-meta text-muted-foreground', phone.current ? 'basis-full' : 'flex-1')}>
			{@render hint()}
		</span>
	{:else if !phone.current}
		<span class="flex-1"></span>
	{/if}
	{#if !phone.current}{@render trail?.()}{/if}
	{#if actions}
		<div
			class={cn('flex gap-2', phone.current && 'grid flex-1 basis-full auto-cols-fr grid-flow-col')}
		>
			{@render actions()}
		</div>
	{/if}
</div>
