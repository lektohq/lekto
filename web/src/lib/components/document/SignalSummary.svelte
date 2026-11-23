<script lang="ts">
	import type { components } from '#lib/api/schema.ts';
	import type { Lookup } from '#lib/masterdata.svelte.ts';
	import { signalSummary } from '#lib/signals.ts';

	// What a signal said in one run: the proposal, names and identifiers in the text, or why it
	// abstained; for the fields node, whether each value stands by its label (rows by place: two
	// fields may share a name). Words only: a document opens in the Beam, from `StepDetails`.
	let { entry, lookup }: { entry: components['schemas']['LogEntry']; lookup: Lookup | null } =
		$props();

	const rows = $derived(signalSummary(entry, lookup));
</script>

{#each rows as row, rowIndex (rowIndex)}
	<dt class="text-muted-foreground">{row.label}</dt>
	<dd class="flex min-w-0 flex-wrap gap-x-3 gap-y-0.5 break-words">
		{#each row.items as item, index (index)}
			<span>{item.text}</span>
		{/each}
	</dd>
{/each}
