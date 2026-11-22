<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.ts';
	import { TONE_EDGE, TONE_FILL, type Lane } from '#lib/tones.ts';
	import { cn } from '#lib/utils.ts';

	// One figure with its word below (web/DESIGN.md, "Cards"): the tile of the system page's
	// tabs. `quiet` stands on the surface (a tile inside a card, a figure of what is over); a
	// lane's tone says how the figure stands, with the lane's ground, text and edge from
	// `tones.ts`. `kind` is the figure's type: a big number, a smaller value with its unit, or
	// a technical name in code.
	const KINDS = {
		figure: 'text-figure',
		value: 'text-lg font-semibold',
		code: 'pt-1 font-mono text-sm font-semibold break-all'
	};

	let {
		value,
		label,
		hint,
		tone = 'plain',
		kind = 'figure',
		class: className = ''
	}: {
		value: string;
		label: string;
		hint?: string;
		tone?: 'plain' | 'quiet' | Lane;
		kind?: keyof typeof KINDS;
		class?: string;
	} = $props();

	const toned = $derived(tone !== 'plain' && tone !== 'quiet');
</script>

<Card.Root
	size="sm"
	data-tone={tone}
	class={cn(
		'flex flex-col gap-0.5',
		tone === 'quiet' && 'bg-surface',
		tone !== 'plain' && tone !== 'quiet' && [TONE_FILL[tone], TONE_EDGE[tone]],
		className
	)}
>
	<span class={cn('tabular-nums', KINDS[kind])}>{value}</span>
	<span class={cn('text-meta', hint ? 'font-medium' : !toned && 'text-muted-foreground')}>
		{label}
	</span>
	{#if hint}<span class="text-xs text-muted-foreground">{hint}</span>{/if}
</Card.Root>
