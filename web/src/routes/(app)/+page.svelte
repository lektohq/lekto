<script lang="ts">
	import FileText from '@lucide/svelte/icons/file-text';
	import { BASE } from '#lib/base.ts';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
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
	// data; #215), the jobs, and below what is expected (the page "Erwartet" went into it). The
	// way to the documents stands in the head; the tiles two to a row below `lg`, also on a
	// phone, and an odd last one takes the whole row (Tobi, 12.11.2026).
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
</script>

<svelte:head><title>{m.overview_title()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.overview_title()} subtitle={m.overview_subtitle()}>
		{#snippet actions()}
			<a href={`${BASE}/documents`} class={cn(buttonVariants({ variant: 'outline' }))}>
				<FileText aria-hidden="true" />
				{m.overview_documents_go()}
			</a>
		{/snippet}
	</PageHeader>
	<div
		class={cn(
			'grid grid-cols-2 gap-3 sm:gap-4 max-lg:[&>:last-child:nth-child(odd)]:col-span-2',
			session.isAdmin && 'lg:grid-cols-3'
		)}
	>
		<InboxTile />
		{#if session.isAdmin}<IdentifiersTile {counts} {problem} onretry={loadCounts} />{/if}
		<SystemTile />
	</div>
	<ExpectedSection />
</div>
