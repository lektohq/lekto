<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import FieldsPanel from '#lib/components/FieldsPanel.svelte';
	import IdentifiersPanel from '#lib/components/IdentifiersPanel.svelte';
	import MasterDataList from '#lib/components/MasterDataList.svelte';
	import TabBar from '#lib/components/TabBar.svelte';
	import TagsPanel from '#lib/components/TagsPanel.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { session } from '#lib/session.svelte.ts';
	import { MASTER_TABS as TABS, masterTabOf, type MasterTab as Tab } from '#lib/master-tabs.ts';
	import { kindFilter } from '#lib/tag-kinds.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import SortMenu from '#lib/components/SortMenu.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import {
		masterSortOf,
		masterSortShort,
		masterSorts,
		rememberMasterSort,
		type MasterSort,
		type SortedList
	} from '#lib/master-pages.ts';

	// Five tabs: contacts, document types, every kind of tag, fields, and the identifiers no
	// person has confirmed (Tobi, 27.10.2026). The tab stands in the URL (an unknown one is the
	// first); the API refuses everyone but admins. Each tab has its own search (in this browser);
	// all but the identifiers add with the button level with the title (on a phone an icon
	// button). The contacts and the types sort beside the search (Tobi, 12.11.2026): by name or
	// by most documents, in the URL and remembered per list.
	const tab = $derived(masterTabOf(page.url.searchParams));
	const sorted = $derived<SortedList | null>(
		tab === 'contacts' || tab === 'document-types' ? tab : null
	);
	const sort = $derived<MasterSort>(sorted ? masterSortOf(page.url.searchParams, sorted) : 'name');

	/** Sort the list of the tab by `value`, from its first page. */
	function sortBy(value: string) {
		if (!sorted) return;
		const chosen = value as MasterSort;
		rememberMasterSort(sorted, chosen);
		// eslint-disable-next-line svelte/prefer-svelte-reactivity
		const next = new URLSearchParams(page.url.search);
		next.set('sort', chosen);
		next.delete('page');
		void goto(`?${next}`, { reset: false });
	}
	const queries = $state<Record<Tab, string>>({
		contacts: '',
		'document-types': '',
		tags: '',
		fields: '',
		identifiers: ''
	});
	const ADD: Record<Exclude<Tab, 'identifiers'>, () => string> = {
		contacts: m.master_add_contact,
		'document-types': m.master_add_type,
		tags: m.master_add_tag,
		fields: m.master_add_field
	};
	const SEARCH: Record<Tab, () => string> = {
		contacts: m.master_search_contacts,
		'document-types': m.master_search_types,
		tags: m.master_search_tags,
		fields: m.master_search_fields,
		identifiers: m.master_search_identifiers
	};
	const LABEL: Record<Tab, () => string> = {
		contacts: m.master_contacts,
		'document-types': m.master_types,
		tags: m.master_tags,
		fields: m.master_fields,
		identifiers: m.master_identifiers
	};

	/** A new item of the tab; on the Tags tab of the kind it shows, else the kind comes first. */
	function add() {
		if (tab === 'identifiers') return;
		if (tab === 'tags') masterDataDialogs.open(kindFilter(page.url.searchParams) ?? 'any-tag');
		else masterDataDialogs.open(tab);
	}
</script>

<svelte:head><title>{m.nav_master_data()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.nav_master_data()}>
		{#snippet actions()}
			{#if tab === 'identifiers'}
				<!-- Identifiers are confirmed, not created here. -->
			{:else if session.isAdmin && phone.current}
				<IconButton label={ADD[tab]()} variant="default" onclick={add}>
					<Plus aria-hidden="true" />
				</IconButton>
			{:else if session.isAdmin}
				<Button onclick={add}>
					<Plus aria-hidden="true" />
					{ADD[tab]()}
				</Button>
			{/if}
		{/snippet}
	</PageHeader>

	{#if !session.isAdmin}
		<p class="text-muted-foreground">{m.admin_only()}</p>
	{:else}
		<div>
			<!-- On a phone a shorter name for the types; five tabs are wider than a phone, so they
			     scroll sideways with the cut edge faded (web/DESIGN.md, "Tabs and switches"). -->
			<TabBar
				label={m.nav_master_data()}
				tabs={TABS.map((value) => ({
					key: value,
					href: `?tab=${value}`,
					label:
						value === 'document-types' && phone.current ? m.master_types_short() : LABEL[value]()
				}))}
				current={tab}
			/>
			<div class="mt-4 flex flex-col gap-3 sm:gap-4">
				<div class="flex items-center gap-2">
					<SearchField
						bind:value={queries[tab]}
						class="min-w-0 flex-1"
						label={m.master_search_label({ what: LABEL[tab]() })}
						placeholder={SEARCH[tab]()}
					/>
					{#if sorted}
						<SortMenu
							options={masterSorts()}
							value={sort}
							short={masterSortShort(sort)}
							onchange={sortBy}
							compact={phone.current}
							class="shrink-0"
						/>
					{/if}
				</div>
				{#key tab}
					{#if tab === 'fields'}
						<FieldsPanel query={queries.fields} />
					{:else if tab === 'identifiers'}
						<IdentifiersPanel query={queries.identifiers} />
					{:else if tab === 'tags'}
						<TagsPanel query={queries.tags} />
					{:else}
						<MasterDataList kind={tab} query={queries[tab]} {sort} />
					{/if}
				{/key}
			</div>
		</div>
	{/if}
</div>
