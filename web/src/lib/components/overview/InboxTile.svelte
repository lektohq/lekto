<script lang="ts">
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import InboxIcon from '@lucide/svelte/icons/inbox';
	import OctagonX from '@lucide/svelte/icons/octagon-x';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import { BASE } from '#lib/base.ts';
	import Figure from '#lib/components/overview/Figure.svelte';
	import Tile from '#lib/components/overview/Tile.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Skeleton } from '#lib/components/ui/skeleton/index.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { inbox } from '#lib/inbox.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The inbox on the overview: everything open and, while there is, its lanes (badges with icon
	// and word), from the counter the header keeps up to date. No line under them (Tobi,
	// 12.11.2026).
	const summary = $derived(inbox.summary);
	const href = `${BASE}/inbox`;
</script>

<Tile title={m.nav_inbox()} icon={InboxIcon} {href} go={m.overview_inbox_go()}>
	{#if !summary}
		<Skeleton class="h-9 w-24" />
	{:else}
		<Figure count={summary.open} label={m.overview_open()} />
		{#if summary.open > 0}
			<ul class="flex flex-wrap gap-1.5">
				{#if summary.intervene > 0}
					<li>
						<Badge variant="red"
							><OctagonX aria-hidden="true" />{m.overview_lane_red({
								count: formatNumber(summary.intervene)
							})}</Badge
						>
					</li>
				{/if}
				{#if summary.review > 0}
					<li>
						<Badge variant="yellow"
							><TriangleAlert aria-hidden="true" />{m.overview_lane_yellow({
								count: formatNumber(summary.review)
							})}</Badge
						>
					</li>
				{/if}
				{#if summary.new > 0}
					<li>
						<Badge variant="green"
							><CircleCheck aria-hidden="true" />{m.overview_lane_new({
								count: formatNumber(summary.new)
							})}</Badge
						>
					</li>
				{/if}
			</ul>
		{/if}
	{/if}
</Tile>
