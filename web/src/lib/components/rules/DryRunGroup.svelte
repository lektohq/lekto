<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// A group of a rule's dry run, the same for document and mail rules (web/DESIGN.md, "A
	// rule's dry run"): a card whose head says once what the rule does to all of its items
	// (`head`), how many they are, and folds the group; the items below as rows. A group the
	// rule cannot act on alone (`conflict`) has a yellow head with a warning sign in place of the
	// box that chooses it (`lead`).
	let {
		label,
		count,
		conflict = false,
		open,
		onfold,
		lead,
		head,
		children
	}: {
		/** Names the group (its items, counted). */
		label: string;
		/** The count beside the head ("12 Dokumente"). */
		count: string;
		conflict?: boolean;
		open: boolean;
		onfold: () => void;
		lead?: Snippet;
		head: Snippet;
		children: Snippet;
	} = $props();
</script>

<Card.Root
	as="section"
	size="flush"
	class={cn('overflow-hidden', conflict && 'border-lane-yellow-foreground/35')}
	aria-label={label}
>
	<div
		class={cn(
			'flex items-center gap-3 px-4 py-3',
			open && 'border-b',
			conflict ? 'bg-lane-yellow/40' : 'bg-muted/50'
		)}
	>
		{#if conflict}
			<TriangleAlert class="size-4 shrink-0 text-lane-yellow-foreground" aria-hidden="true" />
		{:else if lead}
			{@render lead()}
		{/if}
		<div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1.5">
			{@render head()}
		</div>
		<span class="shrink-0 text-sm text-muted-foreground">{count}</span>
		<IconButton
			size="sm"
			label={open ? m.rule_group_fold() : m.rule_group_unfold()}
			aria-expanded={open}
			onclick={onfold}
		>
			<ChevronDown
				class={cn('transition-transform motion-reduce:transition-none', open && 'rotate-180')}
				aria-hidden="true"
			/>
		</IconButton>
	</div>
	{#if open}
		<ul class="divide-y">{@render children()}</ul>
	{/if}
</Card.Root>
