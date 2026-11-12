<script lang="ts">
	import { formatNumber } from '#lib/i18n.ts';

	// The big number of a tile and what it counts; in a narrow tile the word goes under it.
	let { count, label }: { count: number; label: string } = $props();
</script>

<p class="flex flex-wrap items-baseline gap-x-2">
	<span class="text-figure tabular-nums">{formatNumber(count)}</span>
	<span class="text-muted-foreground">{label}</span>
</p>
