<script lang="ts" module>
	/** What a condition's row gets from its group: removing it and moving it up or down. */
	export interface RowMoves {
		onremove: () => void;
		onup?: () => void;
		ondown?: () => void;
	}
</script>

<script lang="ts" generics="C extends TreeCondition">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ListPlus from '@lucide/svelte/icons/list-plus';
	import Plus from '@lucide/svelte/icons/plus';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Snippet } from 'svelte';
	import ConditionGroup from '#lib/components/rules/ConditionGroup.svelte';
	import ModeSelect from '#lib/components/rules/ModeSelect.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { move, newGroup, type TreeCondition, type TreeGroup } from '#lib/rules/tree.ts';
	import { cn } from '#lib/utils.ts';

	// A group of conditions of any kind of rule (Tobi, 05.11.2026: one set of parts for all
	// rules): and/or, turned around or not, with conditions and subgroups. The kind gives the
	// row of a condition (`row`), a new condition (`newCondition`) and its limits; the group
	// does the rest, the same for document and mail rules. `root`: the rule's own group (a
	// card); `top`: a condition step's own group (no frame of its own); `empty`: what an empty
	// root says (a mail rule without conditions takes every mail).
	let {
		group,
		errors,
		row,
		newCondition,
		canAddCondition,
		canAddGroup,
		root = false,
		top = false,
		empty,
		onremove,
		onup,
		ondown
	}: {
		group: TreeGroup<C>;
		errors: Record<string, string>;
		row: Snippet<[C, RowMoves]>;
		newCondition: () => C;
		canAddCondition: boolean;
		canAddGroup: (group: TreeGroup<C>) => boolean;
		root?: boolean;
		top?: boolean;
		empty?: string;
		onremove?: () => void;
		onup?: () => void;
		ondown?: () => void;
	} = $props();

	const own = $derived(root || top);
	const error = $derived(errors[group.key]);

	const remove = (index: number) => group.items.splice(index, 1);
	const up = (index: number) => (index > 0 ? () => move(group.items, index, -1) : undefined);
	const down = (index: number) =>
		index < group.items.length - 1 ? () => move(group.items, index, 1) : undefined;
</script>

<div
	class={cn(
		'flex flex-col gap-3 rounded-2xl border p-3',
		own ? 'bg-card' : 'border-dashed bg-secondary/40',
		top && 'border-0 p-0',
		error && 'border-destructive'
	)}
	data-key={group.key}
	role="group"
	aria-label={own ? m.rule_conditions() : m.rule_subgroup()}
>
	<div class="flex flex-wrap items-center gap-2">
		<ModeSelect value={group.mode} onchange={(mode) => (group.mode = mode)} />
		<Choice bind:checked={group.negate}>{m.rule_negate()}</Choice>
		{#if !own}
			<div class="ml-auto flex gap-0.5">
				<IconButton label={m.rule_move_up()} disabled={!onup} onclick={() => onup?.()}>
					<ArrowUp aria-hidden="true" />
				</IconButton>
				<IconButton label={m.rule_move_down()} disabled={!ondown} onclick={() => ondown?.()}>
					<ArrowDown aria-hidden="true" />
				</IconButton>
				<IconButton label={m.rule_remove()} onclick={onremove}>
					<Trash2 aria-hidden="true" />
				</IconButton>
			</div>
		{/if}
	</div>

	{#each group.items as item, index (item.key)}
		{#if item.kind === 'group'}
			<ConditionGroup
				group={item as TreeGroup<C>}
				{errors}
				{row}
				{newCondition}
				{canAddCondition}
				{canAddGroup}
				onremove={() => remove(index)}
				onup={up(index)}
				ondown={down(index)}
			/>
		{:else}
			{@render row(item as C, {
				onremove: () => remove(index),
				onup: up(index),
				ondown: down(index)
			})}
		{/if}
	{/each}

	{#if empty && own && group.items.length === 0}
		<p class="text-sm text-muted-foreground">{empty}</p>
	{/if}
	{#if error}<Field.Error>{error}</Field.Error>{/if}

	<div class="flex flex-wrap gap-2">
		<Button
			variant="outline"
			size="sm"
			disabled={!canAddCondition}
			onclick={() => group.items.push(newCondition())}
		>
			<Plus aria-hidden="true" />
			{m.rule_add_condition()}
		</Button>
		<Button
			variant="outline"
			size="sm"
			disabled={!canAddGroup(group)}
			onclick={() =>
				group.items.push(newGroup<C>(group.mode === 'all' ? 'any' : 'all', [newCondition()]))}
		>
			<ListPlus aria-hidden="true" />
			{m.rule_add_group()}
		</Button>
	</div>
</div>
