<script lang="ts">
	import type { Snippet } from 'svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import { Separator } from '#lib/components/ui/separator/index.ts';

	// The title of a group of the documents list: a month, a contact, how soon a deadline is
	// (web/DESIGN.md, "Sticky heads"). It sticks below the header where the page says
	// (`--group-top`) until the next group's title pushes it away; on a desktop the tools stand
	// over the end of its line there. As high as a button, it takes no more room in the list
	// than a title of its size (`-my-2`).
	let {
		count = null,
		tone = null,
		children
	}: {
		/** How many documents the group holds, where the page names it (a lens). */
		count?: string | null;
		/** A deadline passed (`overdue`) or near (`soon`). */
		tone?: 'overdue' | 'soon' | null;
		children: Snippet;
	} = $props();
</script>

<SectionTitle
	size="card"
	class={[
		'sticky top-(--group-top) z-20 -my-2 flex h-10 items-center gap-3 bg-background',
		tone === 'overdue' && 'text-lane-red-foreground',
		tone === 'soon' && 'text-lane-yellow-foreground'
	]}
>
	{@render children()}
	{#if count !== null}
		<span class="text-sm font-normal text-muted-foreground tabular-nums">{count}</span>
	{/if}
	<Separator decorative class="flex-1" />
</SectionTitle>
