<script lang="ts" module>
	import { chipStyle, isHex } from '#lib/colors.ts';
	import { cn } from '#lib/utils.ts';

	/** The colours of a chip, a pill like every chip (web/DESIGN.md, "Chips"): filled for a tag,
	 * filled with an edge for a topic, outlined for a group; in `color` where it has one
	 * (`chipStyle` sets the variables). An own colour may be close to the card (white in light,
	 * black in dark): with `ring`, a faint ring keeps a tag's shape. */
	export function chipLook(
		kind: 'tag' | 'topic' | 'group',
		color: string | null | undefined,
		ring = true
	): string {
		const coloured = chipStyle(color) !== null;
		return cn(
			'inline-flex max-w-full min-w-0 items-center gap-1',
			'rounded-full',
			kind === 'topic' && 'border',
			!coloured &&
				(kind === 'topic'
					? 'border-primary/25 bg-primary/10'
					: kind === 'group'
						? 'border bg-background'
						: 'bg-secondary'),
			coloured &&
				(kind === 'group'
					? 'border border-(--chip-fg)/45 bg-background text-(--chip-fg)'
					: cn(
							'bg-(--chip-bg) font-medium text-(--chip-fg)',
							kind === 'topic' && 'border-(--chip-fg)/25'
						)),
			isHex(color) && 'chip-own',
			isHex(color) && kind === 'tag' && ring && 'ring-1 ring-(--chip-fg)/15 ring-inset'
		);
	}
</script>

<script lang="ts">
	import X from '@lucide/svelte/icons/x';
	import LucideIcon from '#lib/components/LucideIcon.svelte';
	import * as Popover from '#lib/components/ui/popover/index.ts';
	import type { Tag } from '#lib/masterdata.svelte.ts';
	import { pathLabel } from '#lib/tags.ts';
	import type { Snippet } from 'svelte';
	import { CHIP_REMOVE } from '#lib/components/Chip.svelte';
	import { steadyText } from '#lib/steady-text.ts';
	import { TONE_FILL } from '#lib/tones.ts';

	// A tag as a chip: its icon and own name in its colour, the path as tooltip and, where
	// `interactive`, on a tap (a phone has no hover); a group outlined, a topic with an edge;
	// `onremove` adds a button that removes it; `onpick` makes the name a button that opens a
	// choice (the one topic of a `TagPicker`). On a phone both take a finger's tap
	// beyond their edges (44 pixels high; the button also to its right, never over the name).
	// With `pressed` it is a toggle, a filter's value (`FacetChips`): chosen, a ring of the
	// primary colour around it keeps its own colour readable, and its name turns bolder at the
	// width it has unchosen (web/DESIGN.md, "Chips", "Steady layout"); `end` follows the name (a
	// count), `title` names it beyond its name (a tag's path). With `change` it shows a change
	// of the tags (web/DESIGN.md, "Change preview"): an added tag green, a removed one red and
	// struck through, each in the lane's tone instead of its own colour.
	let {
		tag,
		group = false,
		topic = false,
		interactive = false,
		size = 'md',
		onremove,
		removeLabel = '',
		onpick,
		pickLabel = '',
		expanded = false,
		pressed,
		onclick,
		title,
		end,
		change
	}: {
		tag: Pick<Tag, 'id' | 'name' | 'path'> & Partial<Pick<Tag, 'icon' | 'color'>>;
		group?: boolean;
		topic?: boolean;
		interactive?: boolean;
		size?: 'sm' | 'md';
		onremove?: () => void;
		removeLabel?: string;
		onpick?: () => void;
		pickLabel?: string;
		/** Whether the choice `onpick` opens is open. */
		expanded?: boolean;
		/** A toggle: chosen or not. */
		pressed?: boolean;
		onclick?: () => void;
		title?: string;
		end?: Snippet;
		change?: 'added' | 'removed';
	} = $props();

	const path = $derived(pathLabel(tag));
	const nested = $derived(tag.path.length > 1);
	const style = $derived(change ? null : chipStyle(tag.color));
</script>

{#if pressed !== undefined}
	<button
		type="button"
		aria-pressed={pressed}
		title={title ?? path}
		{style}
		class={cn(
			// The chosen chip's own ring takes the place of the faint one.
			chipLook(topic ? 'topic' : group ? 'group' : 'tag', tag.color, !pressed),
			size === 'sm' ? 'h-6 px-2 text-xs' : 'h-8 px-3 text-sm',
			'relative transition-shadow max-sm:after:absolute max-sm:after:inset-x-0 max-sm:after:-inset-y-1.5',
			pressed && 'ring-2 ring-primary ring-offset-2 ring-offset-card'
		)}
		{onclick}
	>
		{#if tag.icon}
			<LucideIcon name={tag.icon} class={size === 'sm' ? 'size-3' : 'size-3.5'} />
		{/if}
		<span
			class={cn(
				'steady-weight min-w-0 [--steady-weight:var(--font-weight-semibold)]',
				pressed && 'font-semibold'
			)}
			{@attach steadyText}><span class="truncate">{tag.name}</span></span
		>
		{@render end?.()}
	</button>
{:else}
	<span
		class={cn(
			change
				? cn(chipLook('tag', null), 'font-medium', TONE_FILL[change === 'added' ? 'green' : 'red'])
				: chipLook(topic ? 'topic' : group ? 'group' : 'tag', tag.color),
			size === 'sm' ? 'h-6 px-2 text-xs' : 'h-8 pl-3 text-sm',
			size === 'md' && (onremove ? 'pr-1' : 'pr-3')
		)}
		{style}
		title={path}
		data-color={tag.color ?? undefined}
	>
		{#if tag.icon}
			<LucideIcon name={tag.icon} class={size === 'sm' ? 'size-3' : 'size-3.5'} />
		{/if}
		{#if onpick}
			<button
				type="button"
				class={cn(
					'min-w-0 truncate rounded-full hover:underline',
					size === 'sm' ? 'max-sm:-my-3.5 max-sm:py-3.5' : 'max-sm:-my-3 max-sm:py-3'
				)}
				aria-label={pickLabel}
				aria-haspopup="dialog"
				aria-expanded={expanded}
				onclick={onpick}
			>
				{tag.name}
			</button>
		{:else if interactive && nested}
			<Popover.Root>
				<Popover.Trigger
					class={cn(
						'min-w-0 truncate hover:underline',
						'rounded-full',
						size === 'sm' ? 'max-sm:-my-3.5 max-sm:py-3.5' : 'max-sm:-my-3 max-sm:py-3'
					)}
					aria-label={path}
				>
					{tag.name}
				</Popover.Trigger>
				<Popover.Content class="w-auto max-w-72 px-3 py-2 text-sm" side="top">
					{path}
				</Popover.Content>
			</Popover.Root>
		{:else}
			<span class={cn('min-w-0 truncate', change === 'removed' && 'line-through')}>{tag.name}</span>
		{/if}
		{#if onremove}
			<button type="button" class={CHIP_REMOVE} aria-label={removeLabel} onclick={onremove}>
				<X class="size-3.5" aria-hidden="true" />
			</button>
		{/if}
	</span>
{/if}
