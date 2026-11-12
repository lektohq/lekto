<script lang="ts" generics="T">
	import { untrack, type Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Pagination from '#lib/components/Pagination.svelte';
	import { pageHref, pageOf } from '#lib/master-pages.ts';
	import { rememberedPageSize, type PagedTable } from '#lib/page-size.ts';
	import { pageCount } from '#lib/pagination.ts';

	// One page of a master data list at a time (Tobi, 12.11.2026): `items` are all the search and
	// the filter leave, in their order; `children` draws the page of them, `Pagination` below
	// chooses another (in the link, `?page=`) and the size (remembered for `table`). A new search
	// starts on the first page; a page beyond the last (fewer items after a change) is the last.
	let {
		items,
		table,
		query = '',
		children
	}: {
		items: readonly T[];
		table: PagedTable;
		query?: string;
		children: Snippet<[T[]]>;
	} = $props();

	// The size is remembered for its table, which a tab never changes.
	let size = $state(untrack(() => rememberedPageSize(table)));
	const wanted = $derived(pageOf(page.url.searchParams));
	const last = $derived(pageCount(items.length, size));
	const current = $derived(Math.min(wanted, last));
	const shown = $derived(items.slice((current - 1) * size, current * size));

	/** Show `next` as the page in the link (`replace`: no new history entry, the list changed). */
	function show(next: number, replace = false) {
		void goto(pageHref(page.url, next), replace ? { replace: true, reset: false } : {});
	}

	// The link follows a page that is no longer there.
	$effect(() => {
		if (wanted > last) show(last, true);
	});

	// Typing in the search goes back to the first page; the focus stays in the field.
	let searched = untrack(() => query);
	$effect(() => {
		if (query === searched) return;
		searched = query;
		if (page.url.searchParams.has('page')) show(1, true);
	});

	/** `next` items per page, on the page that holds the first item shown so far. */
	function resize(next: number) {
		const first = (current - 1) * size;
		size = next;
		const target = Math.floor(first / next) + 1;
		if (target !== current) show(target, true);
	}
</script>

<div class="flex flex-col gap-3">
	{@render children(shown)}
	<Pagination page={current} total={items.length} {size} {table} onchange={show} onsize={resize} />
</div>
