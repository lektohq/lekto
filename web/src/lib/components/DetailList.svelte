<script lang="ts">
	import { cn } from '#lib/utils.ts';

	// A few facts of one thing, each a label and a value (DESIGN.md "Lists", "Detail list"): the
	// labels in a column of 7.5 rem, muted; the values beside them, breaking where they must.
	// The card around it gives the padding (`class`).
	let { rows, class: className }: { rows: [string, string][]; class?: string } = $props();
</script>

<dl class={cn('grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm', className)}>
	{#each rows as [label, value] (label)}
		<dt class="text-muted-foreground">{label}</dt>
		<dd class="break-words">{value}</dd>
	{/each}
</dl>
