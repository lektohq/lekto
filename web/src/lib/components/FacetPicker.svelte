<script lang="ts">
	import type { FacetItem } from '#lib/components/FacetList.svelte';
	import { BAR_ACTION } from '#lib/components/PhoneEditorBar.svelte';
	import PhoneSheet from '#lib/components/PhoneSheet.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import TypeIcon from '#lib/components/TypeIcon.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { formatNumber, listLocale } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { byLetter, matchesWords, searchWords, toggled } from '#lib/picking.ts';
	import { ChoiceBox } from '#lib/components/ui/choice/index.ts';

	// Every value of a group of the filters, to search and choose from: by name, under their
	// first letter, each with its count and what it belongs to (`hint`). Choices apply at once.
	// A dialog; on a phone a sheet from the bottom, as every choice from many is there
	// (web/DESIGN.md, "Dialogs, sheets, editors"), with rows of 48 px and no field in focus.
	let {
		open = $bindable(false),
		title,
		searchLabel,
		items,
		selected,
		onchange
	}: {
		open?: boolean;
		title: string;
		searchLabel: string;
		items: readonly FacetItem[];
		selected: readonly string[];
		onchange: (next: string[]) => void;
	} = $props();

	let query = $state('');
	/** "Fertig": closed as by the sheet's or the dialog's own way out, the search forgotten. */
	function close() {
		query = '';
		open = false;
	}
	const sections = $derived.by(() => {
		const words = searchWords(query);
		return byLetter(
			items.filter((item) => matchesWords(item.label, words)),
			listLocale()
		);
	});

	function toggle(id: string, checked: boolean) {
		onchange(toggled(selected, id, checked));
	}
</script>

{#snippet list()}
	{#each sections as section, index (index)}
		<div class="px-2 pt-2 pb-0.5 text-xs font-semibold text-muted-foreground">
			{section.letter}
		</div>
		<ul class="flex flex-col">
			{#each section.items as item (item.id)}
				<li>
					<label
						class="flex min-h-10 cursor-pointer items-center gap-3 rounded-lg px-2 text-sm hover:bg-secondary max-sm:min-h-12"
					>
						<ChoiceBox
							checked={selected.includes(item.id)}
							onchange={(event) => toggle(item.id, event.currentTarget.checked)}
						/>
						<TypeIcon icon={item.icon} class="size-3.5 shrink-0 text-muted-foreground" />
						<span class="min-w-0 flex-1 truncate" title={item.title ?? item.label}>
							{item.label}
						</span>
						{#if item.hint}
							<span class="max-w-[40%] shrink-0 truncate text-xs text-muted-foreground">
								{item.hint}
							</span>
						{/if}
						{#if item.count !== null}
							<span class="w-8 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
								{formatNumber(item.count)}
							</span>
						{/if}
					</label>
				</li>
			{/each}
		</ul>
	{/each}
{/snippet}

{#snippet done()}
	<Button variant="ghost" class={BAR_ACTION} onclick={close}>
		{m.facet_done()}
	</Button>
{/snippet}

{#if phone.current}
	<PhoneSheet bind:open {title} onOpenChange={(next) => next || (query = '')} close={done}>
		<div class="shrink-0 px-4 pb-3">
			<SearchField bind:value={query} label={searchLabel} />
		</div>
		<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 pb-4">
			{@render list()}
		</div>
	</PhoneSheet>
{:else}
	<Dialog.Root bind:open onOpenChange={(next) => next || (query = '')}>
		<Dialog.Content size="md" class="flex max-h-[85dvh] flex-col gap-3">
			<Dialog.Header>
				<Dialog.Title>{title}</Dialog.Title>
			</Dialog.Header>
			<SearchField bind:value={query} label={searchLabel} />
			<div class="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
				{@render list()}
			</div>
			<Dialog.Footer>
				<Button onclick={close}>{m.facet_done()}</Button>
			</Dialog.Footer>
		</Dialog.Content>
	</Dialog.Root>
{/if}
