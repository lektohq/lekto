<script lang="ts">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { moveKeepingFocus, removeKeepingFocus } from '#lib/rules/row-focus.ts';

	// A row of a rule's conditions or actions, the same for document and mail rules: its label
	// (an action names its kind), its fields, then moving it up and down where the order counts
	// (`moves`) and removing it where it may go (`onremove`), and its error below. `name` says
	// which row it is ("Bedingung 2"): the buttons bear it in their names, as every icon button
	// of a list names its object, and show the plain word on hover. The focus stays with the
	// row when it moves or goes (`lib/rules/row-focus.ts`).
	let {
		key,
		label,
		name,
		error = null,
		moves = false,
		onup,
		ondown,
		onremove,
		children
	}: {
		key?: string | number;
		label?: string;
		name?: string;
		error?: string | null;
		/** Up and down: the order counts (a document rule's conditions and actions). */
		moves?: boolean;
		onup?: () => void;
		ondown?: () => void;
		onremove?: () => void;
		children: Snippet;
	} = $props();
</script>

<div class="flex flex-col gap-2 rounded-xl border bg-background p-3" data-key={key} data-rule-row>
	<div class="flex flex-wrap items-start gap-2">
		{#if label}<span class="w-full pt-2 text-sm font-medium sm:w-44">{label}</span>{/if}
		{@render children()}
		{#if moves || onremove}
			<div class="ml-auto flex gap-0.5">
				{#if moves}
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
				{/if}
				{#if onremove}
					<IconButton
						data-row="remove"
						label={name ? m.rule_remove_of({ name }) : m.rule_remove()}
						hint={m.rule_remove()}
						onclick={(event) => void removeKeepingFocus(event.currentTarget, onremove)}
					>
						<Trash2 aria-hidden="true" />
					</IconButton>
				{/if}
			</div>
		{/if}
	</div>
	{#if error}<Field.Error>{error}</Field.Error>{/if}
</div>
