<script lang="ts" module>
	/** A step of the stepper: a link, an action, or none (at the first or the last). */
	export type Step = string | (() => void) | null;
</script>

<script lang="ts">
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import IconButton from '#lib/components/IconButton.svelte';
	import { cn } from '#lib/utils.ts';

	// Previous and next through a row of things, with where one stands ("Dokument 2 von 31"):
	// web/DESIGN.md, "Stepper". The two arrows stand together at the edge the stepper stands at,
	// the text on the other side (`start`: "‹ › Text", `end`: "Text ‹ ›"), so that they stay
	// where they are however long the text grows while one pages; at the first and the last
	// the arrow is disabled, never gone.
	let {
		label,
		text,
		side,
		previous,
		next,
		previousLabel,
		nextLabel,
		class: className
	}: {
		/** The name of the navigation ("Dokumente der Liste"). */
		label: string;
		/** Where one stands ("Dokument 2 von 31"). */
		text: string;
		/** The edge it stands at: the arrows stand there. */
		side: 'start' | 'end';
		previous: Step;
		next: Step;
		previousLabel: string;
		nextLabel: string;
		class?: string;
	} = $props();
</script>

{#snippet arrow(step: Step, name: string, forward: boolean)}
	{#if typeof step === 'string'}
		<IconButton href={step} variant="outline" size="sm" label={name}>
			{#if forward}<ChevronRight aria-hidden="true" />{:else}<ChevronLeft aria-hidden="true" />{/if}
		</IconButton>
	{:else}
		<IconButton
			variant="outline"
			size="sm"
			label={name}
			disabled={step === null}
			onclick={() => step?.()}
		>
			{#if forward}<ChevronRight aria-hidden="true" />{:else}<ChevronLeft aria-hidden="true" />{/if}
		</IconButton>
	{/if}
{/snippet}

{#snippet where()}
	<span class="text-sm whitespace-nowrap text-muted-foreground tabular-nums" aria-live="polite"
		>{text}</span
	>
{/snippet}

<nav aria-label={label} class={cn('flex items-center gap-2', className)}>
	{#if side === 'end'}{@render where()}{/if}
	<div class="flex shrink-0 items-center gap-1">
		{@render arrow(previous, previousLabel, false)}
		{@render arrow(next, nextLabel, true)}
	</div>
	{#if side === 'start'}{@render where()}{/if}
</nav>
