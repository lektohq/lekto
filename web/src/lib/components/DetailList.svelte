<script lang="ts" module>
	import type { Snippet } from 'svelte';

	/** A row: a label and its text, or a label and a snippet with what it shows (chips, before
	 * and after), rendered with the third element. */
	export type DetailRow = [string, string | Snippet] | [string, Snippet<[string]>, string];
</script>

<script lang="ts">
	import { cn } from '#lib/utils.ts';

	// A few facts of one thing, each a label and a value (DESIGN.md "Lists", "Detail list"): the
	// labels in a column of 7.5 rem, muted; the values beside them, breaking where they must. The
	// card around it gives the padding (`class`).
	let { rows, class: className }: { rows: DetailRow[]; class?: string } = $props();
</script>

<dl class={cn('grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm', className)}>
	{#each rows as row (row[0])}
		<dt class="text-muted-foreground">{row[0]}</dt>
		<dd class="break-words">
			{#if row.length === 3}{@render row[1](
					row[2]
				)}{:else if typeof row[1] === 'string'}{row[1]}{:else}{@render row[1]()}{/if}
		</dd>
	{/each}
</dl>
