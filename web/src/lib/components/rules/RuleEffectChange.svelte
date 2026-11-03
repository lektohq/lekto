<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import TagChip from '#lib/components/TagChip.svelte';
	import { describeValue, fieldLabel } from '#lib/describe.ts';
	import type { Lookup, Tag } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	// One change a rule makes, as the head of a dry run's group says it (web/DESIGN.md, "A rule's
	// dry run"): the field, the old value struck through where it is the same on every document,
	// an arrow, the new value; a topic or tags as their chips, tags as those added and removed.
	let {
		field,
		old,
		next,
		lookup
	}: {
		field: string;
		/** Undefined: the documents have different old values. */
		old?: unknown;
		next: unknown;
		lookup: Lookup | null;
	} = $props();

	const tagOf = (id: unknown): Tag | undefined =>
		typeof id === 'string' ? lookup?.tags.find((tag) => tag.id === id) : undefined;
	const list = (value: unknown): unknown[] =>
		Array.isArray(value) ? value : value === null || value === undefined ? [] : [value];

	const chips = $derived(field === 'tags' || field === 'topic');
	const added = $derived(
		field === 'tags' ? list(next).filter((id) => !list(old).includes(id)) : list(next)
	);
	const removed = $derived(
		field === 'tags' && old !== undefined ? list(old).filter((id) => !list(next).includes(id)) : []
	);
</script>

{#snippet chip(id: unknown)}
	{@const tag = tagOf(id)}
	{#if tag}
		<TagChip {tag} topic={tag.scope === 'topic'} size="sm" />
	{:else}
		<span class="font-medium">{describeValue(id, lookup)}</span>
	{/if}
{/snippet}

<span class="inline-flex max-w-full min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
	<span class="text-muted-foreground">{fieldLabel(field, lookup)}</span>
	{#if chips && field === 'tags'}
		{#each added as id (id)}
			<span class="sr-only">{m.rule_change_added()}</span>
			<span class="text-muted-foreground" aria-hidden="true">+</span>{@render chip(id)}
		{/each}
		{#each removed as id (id)}
			<span class="sr-only">{m.rule_change_removed()}</span>
			<span class="text-muted-foreground" aria-hidden="true">−</span>
			<s class="text-muted-foreground">{describeValue(id, lookup)}</s>
		{/each}
	{:else}
		{#if old !== undefined}
			<s class="text-muted-foreground">{describeValue(old, lookup)}</s>
			<span class="sr-only">{m.rule_change_to()}</span>
			<ArrowRight class="size-3.5 text-muted-foreground" aria-hidden="true" />
		{/if}
		{#if chips}
			{#each added as id (id)}{@render chip(id)}{/each}
			{#if added.length === 0}<span class="font-medium">{m.value_unset()}</span>{/if}
		{:else}
			<span class="font-medium">{describeValue(next, lookup)}</span>
		{/if}
	{/if}
</span>
