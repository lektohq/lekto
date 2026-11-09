<script lang="ts" module>
	export interface ChipItem {
		id: string;
		label: string;
		/** A tag's path as the native title (web/DESIGN.md, "Help and tooltips": the names of
		 * options in pickers); none for a plain value, whose label is all it has. */
		title?: string;
		count: number | null;
		/** A tag's colour (palette name or `#rrggbb`), as its chip shows it elsewhere. */
		color?: string | null;
		icon?: string | null;
	}
</script>

<script lang="ts">
	import Chip from '#lib/components/Chip.svelte';
	import LucideIcon from '#lib/components/LucideIcon.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import { formatNumber } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { flipped } from '#lib/picking.ts';
	import { Button } from '#lib/components/ui/button/index.ts';

	// Values of the filters as the chips they are everywhere (web/DESIGN.md, "Chips"): a tag, a
	// topic or a group as a `TagChip` toggle in its colour, chosen with a ring; a plain value as a
	// `Chip` toggle, chosen in the selected look; the count in the chip. 24 px on a desktop, 32 px
	// with a finger's 44 px of hit area on a phone (Tobi, 09.11.2026). The first `limit` show and
	// the chosen ones; `more` (a label) shows the rest on a tap.
	let {
		items,
		selected,
		onchange,
		look = 'tag',
		label,
		limit = Infinity,
		more
	}: {
		items: readonly ChipItem[];
		selected: readonly string[];
		onchange: (next: string[]) => void;
		look?: 'tag' | 'topic' | 'group' | 'plain';
		/** The name of the group of chips, for screen readers. */
		label: string;
		limit?: number;
		more?: (count: number) => string;
	} = $props();

	let open = $state(false);
	const shown = $derived(
		open ? items : items.filter((item, index) => index < limit || selected.includes(item.id))
	);

	const size = $derived(phone.current ? 'md' : 'sm');

	function toggle(id: string) {
		onchange(flipped(selected, id));
	}
</script>

{#if items.length > 0}
	<div class="flex flex-col items-start gap-2">
		<!-- On a phone the rows keep their hit areas apart. -->
		<div
			class={phone.current ? 'flex flex-wrap gap-x-1.5 gap-y-3' : 'flex flex-wrap gap-1.5'}
			role="group"
			aria-label={label}
		>
			{#each shown as item (item.id)}
				{@const active = selected.includes(item.id)}
				{#if look === 'plain'}
					<Chip {size} pressed={active} onclick={() => toggle(item.id)}>
						{#snippet icon()}
							{#if item.icon}<LucideIcon name={item.icon} class="size-3 shrink-0" />{/if}
						{/snippet}
						{item.label}{#if item.count !== null}<span class="ml-1 tabular-nums opacity-70"
								>{formatNumber(item.count)}</span
							>{/if}
					</Chip>
				{:else}
					<TagChip
						tag={{
							id: item.id,
							name: item.label,
							path: [item.label],
							color: item.color,
							icon: item.icon
						}}
						topic={look === 'topic'}
						group={look === 'group'}
						{size}
						pressed={active}
						title={item.title}
						onclick={() => toggle(item.id)}
					>
						{#snippet end()}
							{#if item.count !== null}
								<span class="shrink-0 tabular-nums opacity-70">{formatNumber(item.count)}</span>
							{/if}
						{/snippet}
					</TagChip>
				{/if}
			{/each}
		</div>
		{#if more && items.length > limit}
			<Button
				variant="link"
				size="inline"
				class="text-sm font-normal"
				aria-expanded={open}
				onclick={() => (open = !open)}
			>
				{open ? m.facet_fewer() : more(items.length)}
			</Button>
		{/if}
	</div>
{/if}
