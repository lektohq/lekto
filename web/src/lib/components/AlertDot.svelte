<script lang="ts">
	import { cn } from '#lib/utils.ts';

	// A dot beside a label that something there needs a look (web/DESIGN.md, "Tabs and switches":
	// counts and dots sit beside the label): 8 px, red for an error, yellow for something to
	// check, with its words for a screen reader, since state is never colour alone.
	let {
		tone = 'red',
		label,
		class: className
	}: { tone?: 'red' | 'yellow'; label: string; class?: string } = $props();
</script>

<span
	class={cn(
		'size-2 shrink-0 rounded-full',
		tone === 'red'
			? 'bg-destructive'
			: 'border-[1.5px] border-lane-yellow-foreground bg-lane-yellow',
		className
	)}
	aria-hidden="true"
></span>
<span class="sr-only">{label}</span>
