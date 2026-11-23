<script lang="ts" module>
	/** What a condition's row gets from its group: which one it is ("Bedingung 2"), removing it
	 * and moving it up or down. */
	export interface RowMoves {
		name: string;
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
	import { cardVariants } from '#lib/components/ui/card/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { moveKeepingFocus, removeKeepingFocus } from '#lib/rules/row-focus.ts';
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
		name,
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
		/** Which group of its list it is ("Gruppe 2"), for the names of its buttons. */
		name?: string;
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
		cardVariants({ size: 'sm', tone: own ? 'plain' : 'nested' }),
		'flex flex-col gap-3',
		top && 'border-0 p-0',
		error && 'border-destructive'
	)}
	data-key={group.key}
	data-rule-row={own ? undefined : ''}
	role="group"
	aria-label={own ? m.rule_conditions() : m.rule_subgroup()}
>
	<div class="flex flex-wrap items-center gap-2">
		<ModeSelect value={group.mode} onchange={(mode) => (group.mode = mode)} />
		<Choice bind:checked={group.negate}>{m.rule_negate()}</Choice>
		{#if !own}
			<div class="ml-auto flex gap-0.5">
				<IconButton
					data-row="up"
					label={name ? m.rule_move_up_of({ name }) : m.rule_move_up()}
					hint={m.rule_move_up()}
					disabled={!onup}
					onclick={(event) => void moveKeepingFocus(event.currentTarget, () => onup?.())}
				>
					<ArrowUp aria-hidden="true" />
				</IconButton>
				<IconButton
					data-row="down"
					label={name ? m.rule_move_down_of({ name }) : m.rule_move_down()}
					hint={m.rule_move_down()}
					disabled={!ondown}
					onclick={(event) => void moveKeepingFocus(event.currentTarget, () => ondown?.())}
				>
					<ArrowDown aria-hidden="true" />
				</IconButton>
				<IconButton
					data-row="remove"
					label={name ? m.rule_remove_of({ name }) : m.rule_remove()}
					hint={m.rule_remove()}
					onclick={(event) => void removeKeepingFocus(event.currentTarget, () => onremove?.())}
				>
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
				name={m.rule_row_group({ number: index + 1 })}
				onremove={() => remove(index)}
				onup={up(index)}
				ondown={down(index)}
			/>
		{:else}
			{@render row(item as C, {
				name: m.rule_row_condition({ number: index + 1 }),
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
			data-row="add"
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
