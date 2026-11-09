<script lang="ts" generics="T extends { id: string }">
	import type { Snippet } from 'svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import Pagination from '#lib/components/Pagination.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import * as Table from '#lib/components/ui/table/index.ts';
	import { describeError } from '#lib/errors.ts';
	import type { PagedTable } from '#lib/page-size.ts';
	import type { Pager } from '#lib/paging.svelte.ts';

	// The log of a webhook or a mailbox (web/DESIGN.md, "Intake channels"): a card with its title,
	// a table page by page and its states: a failed load, nothing yet, nothing for the choice, the
	// rows, loading. The page keeps its columns (`head`, `row`) and its filters above the card.
	let {
		id,
		title,
		pager,
		filtered,
		none,
		noneChosen,
		table,
		tableClass,
		tip,
		aside,
		head,
		row
	}: {
		/** The id of the title, which names the card. */
		id: string;
		title: string;
		pager: Pager<T>;
		/** Whether a filter is chosen: then an empty log says nothing fits the choice. */
		filtered: boolean;
		none: string;
		noneChosen: string;
		/** The key under which `Pagination` remembers the page size. */
		table: PagedTable;
		/** The table's class, its least width above all. */
		tableClass: string;
		/** Help beside the title. */
		tip?: Snippet;
		/** A line at the right of the title (how long the log keeps). */
		aside?: Snippet;
		head: Snippet;
		row: Snippet<[T]>;
	} = $props();
</script>

<Card.Root as="section" size="lg" aria-labelledby={id}>
	<div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
		<div class="flex items-center gap-1">
			<SectionTitle {id} size="card">{title}</SectionTitle>
			{@render tip?.()}
		</div>
		{@render aside?.()}
	</div>
	{#if pager.error && !pager.loaded}
		<div class="mt-3">
			<LoadProblem problem={describeError(pager.error)} onretry={() => pager.reload()} />
		</div>
	{:else if pager.empty}
		<p class="mt-3 text-muted-foreground">{filtered ? noneChosen : none}</p>
	{:else if pager.items.length}
		<div class="mt-3">
			<Table.Root class={tableClass}>
				<Table.Header>
					<Table.Row class="text-xs text-muted-foreground">
						{@render head()}
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each pager.items as item (item.id)}
						{@render row(item)}
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
		<div class="mt-4">
			<Pagination
				page={pager.page}
				total={pager.total}
				size={pager.size}
				{table}
				onchange={(next) => pager.go(next)}
				onsize={(next) => pager.resize(next)}
			/>
		</div>
	{:else}
		<Loading class="mt-3" />
	{/if}
</Card.Root>
