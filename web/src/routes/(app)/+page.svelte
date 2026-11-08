<script lang="ts">
	import ExpectedSection from '#lib/components/overview/ExpectedSection.svelte';
	import IdentifiersTile from '#lib/components/overview/IdentifiersTile.svelte';
	import InboxTile from '#lib/components/overview/InboxTile.svelte';
	import SystemTile from '#lib/components/overview/SystemTile.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import { onMount } from 'svelte';
	import { describeError } from '#lib/errors.ts';
	import { type OpenCounts, openCounts } from '#lib/open-identifiers.ts';

	// The overview, the start page under the logo (Tobi, 27.10.2026): what waits for someone, each
	// with the way there. The inbox, the suggested identifiers (admins: they keep the master
	// data; only while there are any, #215), the jobs, and below what is expected (the page
	// "Erwartet" went into it).
	let counts = $state<OpenCounts | null>(null);
	let problem = $state<string | null>(null);

	async function loadCounts() {
		try {
			counts = await openCounts();
			problem = null;
		} catch (error) {
			problem = describeError(error);
		}
	}

	onMount(() => {
		if (session.isAdmin) void loadCounts();
	});

	const suggestions = $derived(
		session.isAdmin && (problem !== null || (counts !== null && counts.suggested > 0))
	);
</script>

<svelte:head><title>{m.overview_title()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.overview_title()} subtitle={m.overview_subtitle()} />
	<div class={cn('grid gap-4 sm:grid-cols-2', suggestions && 'lg:grid-cols-3')}>
		<InboxTile />
		{#if suggestions}<IdentifiersTile {counts} {problem} onretry={loadCounts} />{/if}
		<SystemTile />
	</div>
	<ExpectedSection />
</div>
