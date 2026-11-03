<script lang="ts">
	import { tick } from 'svelte';
	import Plus from '@lucide/svelte/icons/plus';
	import CreateOffer from '#lib/components/CreateOffer.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import TagPickerDialog from '#lib/components/TagPickerDialog.svelte';
	import TagPickerList from '#lib/components/TagPickerList.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Popover from '#lib/components/ui/popover/index.ts';
	import type { Tag, TagScope } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { session } from '#lib/session.svelte.ts';
	import { creatable, createWithDetails } from '#lib/tag-create.ts';
	import { pathLabel } from '#lib/tags.ts';
	import Chip from '#lib/components/Chip.svelte';
	import { cn } from '#lib/utils.ts';

	// The one field for tags: a document's tags, a contact's or a type's groups, a contact's
	// topics. Their chips to remove and a dashed button that opens the choice (`TagPickerList`):
	// wider than a phone in a popover at the button, on a phone a sheet from the bottom
	// (`TagPickerDialog`; Tobi, 20.10.2026). A chosen tag missing from `tags` (deleted meanwhile)
	// stays as a chip until removed. An admin's search that finds no tag named so offers to
	// create one in the tag dialog (`tag-create.ts`), chosen when made; `oncreated` tells the
	// editor. `offered`
	// narrows what may be chosen (a document: no tag above one set). `single`: one tag at most (a
	// document's topic; Tobi, 03.11.2026): radios, a click chooses and closes, the chosen chip's
	// name opens the choice again, and no "+" chip while one is chosen.
	let {
		id,
		label,
		labelledby,
		title,
		scope,
		tags,
		selected,
		onchange,
		offered,
		disabled = false,
		oncreated = () => {},
		single = false,
		creating = true,
		placeholder
	}: {
		id: string;
		/** What the chips are ("Groups"). */
		label: string;
		/** The id of a visible label of the chips, named so instead of by `label`. */
		labelledby?: string;
		/** The choice's title, the tags of the scope ("Contact groups"). */
		title: string;
		scope: TagScope;
		tags: readonly Tag[];
		selected: readonly string[];
		onchange: (selected: string[]) => void;
		offered?: (tag: Tag) => boolean;
		/** Chips only: nothing to add or remove. */
		disabled?: boolean;
		oncreated?: (tag: Tag) => void;
		single?: boolean;
		/** Whether an admin may create a tag from the search. */
		creating?: boolean;
		/** What the field says while nothing is chosen and nothing can be. */
		placeholder?: string;
	} = $props();

	let open = $state(false);
	let query = $state('');
	let search = $state<HTMLInputElement | null>(null);
	let field = $state<HTMLElement | null>(null);
	let content = $state<HTMLElement | null>(null);
	// Tags made here, until `tags` holds them too.
	let made = $state<Tag[]>([]);
	const known = $derived([
		...tags,
		...made.filter((tag) => !tags.some((other) => other.id === tag.id))
	]);
	const canCreate = $derived(creating && session.isAdmin && creatable(known, scope, query));
	const byId = $derived(new Map(known.map((tag) => [tag.id, tag])));
	const chips = $derived(
		[...new Set(selected)].map(
			(value) => byId.get(value) ?? { id: value, name: m.rule_unknown(), path: [m.rule_unknown()] }
		)
	);
	const isTopic = $derived(scope === 'topic');
	const isGroup = $derived(scope === 'contact' || scope === 'document_type');
	const addText = $derived(
		isTopic ? m.picker_add_topic() : isGroup ? m.picker_add_group() : m.picker_add_tag()
	);
	const addLabel = $derived(
		isTopic ? m.picker_add_topic_label() : isGroup ? m.picker_add_group_label() : m.field_tag_add()
	);
	const searchLabel = $derived(
		creating && session.isAdmin ? m.picker_search_create() : m.assignment_search()
	);
	const adds = $derived(!disabled && !(single && chips.length > 0));

	function close() {
		query = '';
		open = false;
	}

	// The choice gives way to the tag dialog; the tag it makes is chosen.
	async function create() {
		const name = query;
		query = '';
		open = false;
		const tag = await createWithDetails(scope, name);
		if (!tag) return;
		made = [...made, tag];
		oncreated(tag);
		onchange(single ? [tag.id] : [...selected, tag.id]);
	}
</script>

{#snippet offers()}
	{#if canCreate}
		<CreateOffer name={query.trim()} onclick={create} />
	{/if}
{/snippet}

{#snippet add(props: Record<string, unknown> = {})}
	<Chip
		variant="add"
		{...props}
		aria-label={addLabel}
		onclick={() => {
			query = '';
			open = true;
		}}
	>
		{#snippet icon()}<Plus class="size-4 shrink-0" aria-hidden="true" />{/snippet}
		{addText}
	</Chip>
{/snippet}

<div
	bind:this={field}
	{id}
	role="group"
	aria-label={labelledby ? undefined : label}
	aria-labelledby={labelledby}
	class="flex min-h-11 min-w-0 flex-wrap items-center gap-2 rounded-xl border border-input bg-card px-1.5 py-1 dark:bg-input/30"
>
	{#each chips as tag (tag.id)}
		<TagChip
			{tag}
			group={isGroup}
			topic={isTopic}
			interactive
			onremove={disabled
				? undefined
				: () => {
						if (single) close();
						onchange(selected.filter((entry) => entry !== tag.id));
					}}
			removeLabel={m.rule_remove_value({ name: pathLabel(tag) })}
			onpick={single && !disabled ? () => (open = !open) : undefined}
			pickLabel={m.picker_change({ name: tag.name })}
			expanded={open}
		/>
	{:else}
		{#if disabled && placeholder}
			<span class="px-1 text-sm text-muted-foreground">{placeholder}</span>
		{/if}
	{/each}
	{#if !disabled}
		{#if phone.current}
			{#if adds}
				{@render add({ 'aria-haspopup': 'dialog', 'aria-expanded': open })}
			{/if}
		{:else}
			<Popover.Root bind:open onOpenChange={(next) => next || (query = '')}>
				{#if adds}
					<Popover.Trigger>
						{#snippet child({ props })}
							{@render add(props)}
						{/snippet}
					</Popover.Trigger>
				{/if}
				<!-- One chosen, its chip opens the choice: placed at the field, which keeps its clicks
				     (the chip's own toggles it), and the focus comes back to the chip. -->
				<Popover.Content
					bind:ref={content}
					align="start"
					collisionPadding={8}
					role="dialog"
					aria-labelledby="{id}-picker-title"
					class="flex max-h-[min(30rem,var(--bits-popover-content-available-height))] w-80 flex-col gap-0 p-0"
					customAnchor={single ? field : undefined}
					onOpenAutoFocus={(event) => {
						event.preventDefault();
						search?.focus();
					}}
					onInteractOutside={(event) => {
						if (single && field?.contains(event.target as Node)) event.preventDefault();
					}}
					onCloseAutoFocus={(event) => {
						if (!single) return;
						event.preventDefault();
						// After the chip of the choice made with the closing click is there, and only
						// where the focus would be lost with the popover (not taken by a click elsewhere).
						void tick().then(() => {
							const at = document.activeElement;
							if (at === document.body || content?.contains(at))
								field?.querySelector('button')?.focus();
						});
					}}
				>
					<div
						class={cn(
							'flex shrink-0 items-center justify-between gap-2 pr-1.5 pl-4',
							single ? 'py-3' : 'py-1.5'
						)}
					>
						<span id="{id}-picker-title" class="text-sm font-semibold">{title}</span>
						{#if !single}
							<Button variant="ghost" size="sm" class="text-brand" onclick={close}>
								{m.picker_done()}
							</Button>
						{/if}
					</div>
					<TagPickerList
						{title}
						{scope}
						tags={known}
						{selected}
						{onchange}
						{offered}
						{searchLabel}
						bind:query
						bind:search
						actions={offers}
						{single}
						onpicked={close}
					/>
				</Popover.Content>
			</Popover.Root>
		{/if}
	{/if}
</div>

{#if phone.current && !disabled}
	<TagPickerDialog
		bind:open
		bind:query
		{title}
		{scope}
		tags={known}
		{selected}
		{onchange}
		{offered}
		{searchLabel}
		actions={offers}
		{single}
	/>
{/if}
