<script lang="ts">
	import IdCard from '@lucide/svelte/icons/id-card';
	import { BASE } from '#lib/base.ts';
	import Figure from '#lib/components/overview/Figure.svelte';
	import Tile from '#lib/components/overview/Tile.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import { Skeleton } from '#lib/components/ui/skeleton/index.ts';
	import type { OpenCounts } from '#lib/open-identifiers.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The suggestions among the open identifiers on the overview (admins; #215): a domain that
	// fits its contact's name, an IBAN for a profile; shown also with none, like the inbox
	// (Tobi, 12.11.2026). The learned ones, which work already, only the tab of master data
	// lists. The page asks for the counts.
	let {
		counts,
		problem,
		onretry
	}: { counts: OpenCounts | null; problem: string | null; onretry: () => void } = $props();
</script>

<Tile
	title={m.master_identifiers()}
	icon={IdCard}
	href={`${BASE}/admin/master-data?tab=identifiers`}
	go={m.overview_identifiers_go()}
>
	{#if problem}
		<div class="relative z-10"><LoadProblem {problem} {onretry} /></div>
	{:else if !counts}
		<Skeleton class="h-9 w-24" />
	{:else}
		<Figure count={counts.suggested} label={m.overview_identifiers_suggestions()} />
	{/if}
</Tile>
