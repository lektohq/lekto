<script lang="ts">
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import InboxIcon from '@lucide/svelte/icons/inbox';
	import OctagonX from '@lucide/svelte/icons/octagon-x';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import type { Component } from 'svelte';
	import { BASE } from '#lib/base.ts';
	import Figure from '#lib/components/overview/Figure.svelte';
	import Tile from '#lib/components/overview/Tile.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Skeleton } from '#lib/components/ui/skeleton/index.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { inbox } from '#lib/inbox.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The inbox on the overview: everything open and, while there is, its lanes (badges with icon
	// and word), from the counter the header keeps up to date. No line under them; on a phone a
	// lane shows icon and number in one row, its word for screen readers (Tobi, 12.11.2026).
	const summary = $derived(inbox.summary);
	const href = `${BASE}/inbox`;
</script>

{#snippet lane(
	variant: 'red' | 'yellow' | 'green',
	Icon: Component,
	count: number,
	label: typeof m.overview_lane_red
)}
	{#if count > 0}
		<li>
			<Badge {variant}
				><Icon aria-hidden="true" /><span class="sm:hidden" aria-hidden="true"
					>{formatNumber(count)}</span
				><span class="max-sm:sr-only">{label({ count: formatNumber(count) })}</span></Badge
			>
		</li>
	{/if}
{/snippet}

<Tile title={m.nav_inbox()} icon={InboxIcon} {href} go={m.overview_inbox_go()}>
	{#if !summary}
		<Skeleton class="h-9 w-24" />
	{:else}
		<Figure count={summary.open} label={m.overview_open()} />
		{#if summary.open > 0}
			<ul class="flex flex-wrap gap-1.5">
				{@render lane('red', OctagonX, summary.intervene, m.overview_lane_red)}
				{@render lane('yellow', TriangleAlert, summary.review, m.overview_lane_yellow)}
				{@render lane('green', CircleCheck, summary.new, m.overview_lane_new)}
			</ul>
		{/if}
	{/if}
</Tile>
