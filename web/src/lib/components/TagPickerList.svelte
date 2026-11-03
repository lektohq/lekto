<script lang="ts">
	import type { Snippet } from 'svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import type { Tag, TagScope } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { toggled } from '#lib/picking.ts';
	import { matchesQuery, ofScope, pathLabel } from '#lib/tags.ts';
	import { ChoiceBox } from '#lib/components/ui/choice/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import Eyebrow from '#lib/components/page/Eyebrow.svelte';

	// Several tags of one scope to choose: a search over their paths, then every tag of the scope
	// that may be chosen (`offered`) with a checkbox, nested as in its tree; while searching the
	// matches with their paths, or all of them when none matches. `actions` stand between the
	// search and the list (the offers to create a tag, which need the query). In a dialog or a
	// popover (`TagPicker`). `single`: one tag at most (a topic), a flat list of radios; a click
	// on one tells `onpicked`, the keys only move the choice.
	let {
		title,
		scope,
		tags,
		selected,
		onchange,
		query = $bindable(''),
		searchLabel = m.assignment_search(),
		offered = () => true,
		search = $bindable(null),
		actions,
		single = false,
		onpicked
	}: {
		/** The tags of the scope ("Contact groups"), for "all …" when nothing matches. */
		title: string;
		scope: TagScope;
		tags: readonly Tag[];
		selected: readonly string[];
		onchange: (selected: string[]) => void;
		query?: string;
		searchLabel?: string;
		/** Whether a tag may be chosen (a chosen one always shows). */
		offered?: (tag: Tag) => boolean;
		/** The search field, for the focus. */
		search?: HTMLInputElement | null;
		actions?: Snippet;
		single?: boolean;
		/** In `single`, a tag clicked: the choice is made. */
		onpicked?: () => void;
	} = $props();

	const radios = $props.id();

	const own = $derived(
		ofScope(tags, scope).filter((tag) => selected.includes(tag.id) || offered(tag))
	);
	const searching = $derived(query.trim() !== '');
	const matches = $derived(searching ? own.filter((tag) => matchesQuery(tag, query)) : own);
	// Nothing found: all of them, to choose from anyway.
	const listed = $derived(searching && matches.length === 0 ? own : matches);
	const isGroup = $derived(scope === 'contact' || scope === 'document_type');

	function toggle(id: string, on: boolean) {
		onchange(single ? (on ? [id] : []) : toggled(selected, id, on));
	}

	// A click by pointer (on the row too: its label passes it on), not the click the keys send
	// to a radio they move to. It chooses before it closes: the change comes after the click.
	function picked(event: MouseEvent, id: string) {
		if (!single || event.detail === 0) return;
		onchange([id]);
		onpicked?.();
	}
</script>

<div class="shrink-0 px-4 pb-3">
	<SearchField bind:ref={search} bind:value={query} label={searchLabel} />
</div>
<div class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain px-4 pb-4">
	{@render actions?.()}
	{#if searching && matches.length === 0}
		<p class="px-1 text-sm text-muted-foreground">{m.picker_no_match()}</p>
		<Eyebrow as="h3" class="mt-2 px-1">
			{m.picker_all({ kind: title })}
		</Eyebrow>
	{/if}
	{#if listed.length > 0}
		<Card.Root as="ul" size="flush" class="shrink-0 divide-y overflow-hidden">
			{#each listed as tag (tag.id)}
				{@const nested = !single && (!searching || matches.length === 0)}
				<li>
					<label
						class="flex min-h-12 cursor-pointer items-center gap-3 py-1.5 pr-3.5 pl-[calc(0.875rem+var(--depth)*1.5rem)] hover:bg-secondary/60"
						style="--depth: {nested ? tag.path.length - 1 : 0}"
					>
						<span class="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-0.5">
							<TagChip
								tag={{ ...tag, path: [tag.name] }}
								group={isGroup}
								topic={scope === 'topic'}
							/>
							{#if !single && !nested && tag.path.length > 1}
								<span class="text-xs text-muted-foreground">{pathLabel(tag)}</span>
							{/if}
						</span>
						<ChoiceBox
							type={single ? 'radio' : 'checkbox'}
							name={single ? radios : undefined}
							aria-label={single ? tag.name : pathLabel(tag)}
							checked={selected.includes(tag.id)}
							onchange={(event) => toggle(tag.id, event.currentTarget.checked)}
							onclick={(event) => picked(event, tag.id)}
						/>
					</label>
				</li>
			{/each}
		</Card.Root>
	{/if}
</div>
