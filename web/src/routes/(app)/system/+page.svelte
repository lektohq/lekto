<script lang="ts">
	import { page } from '$app/state';
	import AutomationTab from '#lib/components/system/AutomationTab.svelte';
	import ClassifierTab from '#lib/components/system/ClassifierTab.svelte';
	import IntakeTab from '#lib/components/system/IntakeTab.svelte';
	import JobsTab from '#lib/components/system/JobsTab.svelte';
	import SearchTab from '#lib/components/system/SearchTab.svelte';
	import TabBar from '#lib/components/TabBar.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';
	import { systemTab, systemTabs, type SystemTab } from '#lib/system.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';

	// The page "System" (Tobi, 24.10.2026): what Lekto does by itself, for every user; acting
	// on it (training, trying jobs again, the maintenance) is for admins, and so is the tab of the
	// intake channels (Tobi, 04.11.2026). The jobs come first, the maintenance is their dialog
	// (Tobi, 12.11.2026). The tab stands in the URL.
	const tab = $derived(systemTab(page.url.searchParams, session.isAdmin));
	const LABELS: Record<SystemTab, () => string> = {
		jobs: m.system_tab_jobs,
		automation: m.system_tab_automation,
		classifier: m.system_tab_classifier,
		search: m.system_tab_search,
		intake: m.system_tab_intake
	};
</script>

<svelte:head><title>{LABELS[tab]()} · {m.nav_system()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.nav_system()} />
	<TabBar
		label={m.system_tabs()}
		tabs={systemTabs(session.isAdmin).map((value) => ({
			key: value,
			href: `?tab=${value}`,
			label: LABELS[value]()
		}))}
		current={tab}
	/>
	{#key tab}
		{#if tab === 'automation'}
			<AutomationTab />
		{:else if tab === 'classifier'}
			<ClassifierTab />
		{:else if tab === 'search'}
			<SearchTab />
		{:else if tab === 'intake'}
			<IntakeTab />
		{:else}
			<JobsTab />
		{/if}
	{/key}
</div>
