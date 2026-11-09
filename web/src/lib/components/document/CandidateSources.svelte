<script lang="ts">
	import Chip from '#lib/components/Chip.svelte';
	import { openBeam } from '#lib/beam.svelte.ts';
	import { quoted } from '#lib/i18n.ts';
	import { sourceChips, type Candidate } from '#lib/candidates.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// What each signal said about a value: a chip per signal (web/DESIGN.md, "Chips"), selected
	// where it counts for the judge, neutral where the signal was not sure enough (said in words
	// for a screen reader; dashed means "empty" or "add"). The similar documents stand as their
	// numbers (web/DESIGN.md, "Beam"): a number shows its document in the Beam, paging through
	// them all; the document checked stays where it is.
	let { candidate, inverted = false }: { candidate: Candidate; inverted?: boolean } = $props();

	const chips = $derived(candidate.sources.flatMap(sourceChips));
</script>

<span class="flex flex-wrap items-center gap-1">
	{#each chips as chip, index (index)}
		<Chip
			size="sm"
			variant={chip.strong ? 'selected' : 'neutral'}
			title={[chip.note, chip.quote && quoted(chip.quote)].filter(Boolean).join(' ') || undefined}
			class={cn('gap-1', inverted && 'border-transparent bg-background/15 text-current')}
		>
			{chip.text}
			{#if chip.quote}<span class="sr-only">: {quoted(chip.quote)}</span>{/if}
			{#if chip.note}<span class="sr-only">({chip.note})</span>{/if}
			{#if !chip.strong}<span class="sr-only">({m.candidate_weak()})</span>{/if}
			{#each chip.documents as id, number (id)}
				<button
					type="button"
					aria-label={m.candidate_document({ number: number + 1 })}
					class={cn(
						'relative font-mono after:absolute after:-inset-1.5 hover:underline max-sm:after:-inset-3',
						inverted ? 'underline' : 'text-brand'
					)}
					onclick={() => openBeam(chip.documents, id, m.signal_neighbours())}
				>
					{number + 1}
				</button>
			{/each}
		</Chip>
	{/each}
</span>
