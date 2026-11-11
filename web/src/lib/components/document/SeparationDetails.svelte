<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import Barcode from '@lucide/svelte/icons/barcode';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { openBeam } from '#lib/beam.svelte.ts';
	import BeamTitle from '#lib/components/BeamTitle.svelte';
	import LaneBadge from '#lib/components/LaneBadge.svelte';
	import { formatNumber } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { pageGroups, partsOf, type PageGroup, type Separation } from '#lib/separation.ts';
	import { summaryOfSheets } from '#lib/step-summary.ts';
	import { type Lane } from '#lib/tones.ts';
	import { cn } from '#lib/utils.ts';

	// The separation drawn (web/DESIGN.md, "Fassung"; Tobi, 11.11.2026): the stack as a row of
	// pages, the separator sheets hatched, each part under a bracket, and where the parts went
	// (this document's next version, the others as documents of their own, each by its title
	// now in the Beam with its lane); for a part of a stack, the stack with its own pages
	// marked; without a sheet, the pages with the codes read on them.
	let { separation }: { separation: Separation } = $props();

	type Brief = { title: string; lane: Lane | null };
	const splitOff = $derived(separation.kind === 'looked' ? separation.splitOff : []);
	let briefs = $state<Record<string, Brief | null>>({});
	$effect(() => {
		const ids = splitOff;
		briefs = {};
		if (ids.length === 0) return;
		let stale = false;
		void (async () => {
			const found: Record<string, Brief | null> = {};
			await Promise.all(
				ids.map(async (id) => {
					try {
						const document = await unwrap(
							api.GET('/api/v1/documents/{id}', { params: { path: { id } } })
						);
						found[id] = { title: document.title, lane: document.lane };
					} catch {
						found[id] = null;
					}
				})
			);
			if (!stale) briefs = found;
		})();
		return () => {
			stale = true;
		};
	});

	const pagesText = (pages: readonly number[]) => {
		const first = String(pages[0]);
		const last = String(pages.at(-1));
		return first === last
			? m.page_edit_part_page({ page: first })
			: m.page_edit_part_pages({ first, last });
	};

	const HATCHED =
		'bg-[repeating-linear-gradient(135deg,var(--border)_0_3px,var(--card)_3px_7px)] text-foreground';

	function view(id: string) {
		const shown = splitOff.filter((each) => briefs[each]);
		openBeam(shown, id, m.tab_processing());
	}
</script>

{#snippet tiles(group: PageGroup, mine: readonly number[], coded: readonly number[])}
	<ol class="flex gap-1.5">
		{#each group.pages as page (page)}
			{@const own = mine.includes(page)}
			<li
				class={cn(
					'relative flex h-12 w-9 items-center justify-center rounded-md border bg-card text-micro text-muted-foreground tabular-nums',
					group.part === null && HATCHED,
					own && 'border-2 border-primary bg-panel font-semibold text-brand',
					mine.length > 0 && !own && 'opacity-50'
				)}
				aria-label={group.part === null
					? m.details_separate_sheet_label({ page: String(page) })
					: m.details_separate_page_label({ page: String(page) })}
			>
				{#if group.part === null}
					<Barcode class="size-4" aria-hidden="true" />
				{:else}
					<span aria-hidden="true">{page}</span>
				{/if}
				{#if coded.includes(page)}
					<span class="absolute top-1 right-1 size-1.5 rounded-xs bg-muted-foreground"></span>
				{/if}
			</li>
		{/each}
	</ol>
{/snippet}

{#snippet strip(groups: PageGroup[], mine: readonly number[], coded: readonly number[])}
	<ol class="flex items-start gap-3 overflow-x-auto pb-1">
		{#each groups as group (group.pages[0])}
			{@const marked = mine.length === 0 ? group.part !== null : mine.includes(group.pages[0])}
			<li class="flex shrink-0 flex-col gap-1">
				{@render tiles(group, mine, coded)}
				{#if group.part === null}
					<span class="h-1.5" aria-hidden="true"></span>
					<span class="text-center text-xs text-muted-foreground">{pagesText(group.pages)}</span>
				{:else if groups.length > 1}
					<span
						class={cn(
							'h-1.5 rounded-b border-2 border-t-0',
							marked ? 'border-primary' : 'border-transparent'
						)}
						aria-hidden="true"
					></span>
					<span
						class={cn(
							'text-center text-xs',
							marked ? 'font-medium text-brand' : 'text-muted-foreground'
						)}
					>
						{mine.length > 0 && marked
							? m.details_separate_this()
							: m.details_separate_part({ part: formatNumber(group.part) })}
					</span>
				{/if}
			</li>
		{/each}
	</ol>
{/snippet}

{#snippet legend(sheet: boolean, code: boolean)}
	{#if sheet || code}
		<p class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
			{#if sheet}
				<span class="flex items-center gap-1.5">
					<span class={cn('size-3.5 rounded-xs border', HATCHED)} aria-hidden="true"></span>
					{m.details_separate_sheet_legend()}
				</span>
			{/if}
			{#if code}
				<span class="flex items-center gap-1.5">
					<span class="size-1.5 rounded-xs bg-muted-foreground" aria-hidden="true"></span>
					{m.details_separate_code_legend()}
				</span>
			{/if}
		</p>
	{/if}
{/snippet}

{#if separation.kind === 'looked'}
	{@const parts = partsOf(separation.pages, separation.sheets)}
	{@const sheet = separation.sheets.length > 0}
	{@const coded = sheet ? [] : [...new Set(separation.codes.map((code) => code.page))]}
	<figure class="m-0 flex flex-col gap-2">
		<figcaption class="flex flex-wrap items-baseline gap-x-2 text-sm">
			<span class="font-medium">
				{sheet ? m.details_separate_stack() : m.details_separate_document()}
			</span>
			<span class="text-xs text-muted-foreground">
				{#if !sheet}
					{m.details_separate_as_it_came({ pages: formatNumber(separation.pages) })}
				{:else if parts.length === 0 || separation.version === null}
					{m.details_separate_only_sheets({ pages: formatNumber(separation.pages) })}
				{:else}
					{m.details_separate_stack_kept({
						pages: formatNumber(separation.pages),
						version: String(separation.version - 1)
					})}
				{/if}
			</span>
		</figcaption>
		{@render strip(pageGroups(separation.pages, separation.sheets), [], coded)}
		{@render legend(sheet, coded.length > 0)}
	</figure>
	{#if sheet && separation.version !== null && parts.length > 0}
		<ul class="flex flex-col rounded-xl border bg-card" aria-label={m.details_separate_parts()}>
			{#each parts as pages, index (pages[0])}
				{@const id = index === 0 ? null : (separation.splitOff[index - 1] ?? null)}
				{@const brief = id ? briefs[id] : undefined}
				<li
					class="flex flex-wrap items-center gap-x-3 gap-y-1 border-t px-3.5 py-2.5 text-sm first:border-t-0"
				>
					<span class="font-semibold">
						{m.details_separate_part({ part: formatNumber(index + 1) })}
					</span>
					<span class="text-muted-foreground tabular-nums">{pagesText(pages)}</span>
					<ArrowRight class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
					{#if index === 0}
						<span>{m.details_separate_to_version({ version: String(separation.version) })}</span>
					{:else if id && brief}
						<BeamTitle title={brief.title} class="text-sm" onview={() => view(id)} />
						<LaneBadge lane={brief.lane} size="md" class="ml-auto shrink-0" />
					{:else if brief === null}
						<span class="text-muted-foreground">{m.details_separate_gone()}</span>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
{:else if separation.kind === 'part' && separation.stackPages > 0}
	<figure class="m-0 flex flex-col gap-2">
		<figcaption class="flex flex-wrap items-baseline gap-x-2 text-sm">
			<span class="font-medium">{m.details_separate_from_stack()}</span>
			<span class="text-xs text-muted-foreground">
				{[
					m.details_separate_stack_pages({ pages: formatNumber(separation.stackPages) }),
					summaryOfSheets(separation.sheets)
				]
					.filter(Boolean)
					.join(' · ')}
			</span>
		</figcaption>
		{@render strip(pageGroups(separation.stackPages, separation.sheets), separation.pages, [])}
		{@render legend(separation.sheets.length > 0, false)}
	</figure>
{/if}
