<script lang="ts">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A row of a rule's conditions or actions, the same for document and mail rules: its label
	// (an action names its kind), its fields, then moving it up and down where the order counts
	// (`moves`) and removing it where it may go (`onremove`), and its error below.
	let {
		key,
		label,
		error = null,
		moves = false,
		onup,
		ondown,
		onremove,
		children
	}: {
		key?: string | number;
		label?: string;
		error?: string | null;
		/** Up and down: the order counts (a document rule's conditions and actions). */
		moves?: boolean;
		onup?: () => void;
		ondown?: () => void;
		onremove?: () => void;
		children: Snippet;
	} = $props();
</script>

<div class="flex flex-col gap-2 rounded-xl border bg-background p-3" data-key={key}>
	<div class="flex flex-wrap items-start gap-2">
		{#if label}<span class="w-full pt-2 text-sm font-medium sm:w-44">{label}</span>{/if}
		{@render children()}
		{#if moves || onremove}
			<div class="ml-auto flex gap-0.5">
				{#if moves}
					<IconButton label={m.rule_move_up()} disabled={!onup} onclick={() => onup?.()}>
						<ArrowUp aria-hidden="true" />
					</IconButton>
					<IconButton label={m.rule_move_down()} disabled={!ondown} onclick={() => ondown?.()}>
						<ArrowDown aria-hidden="true" />
					</IconButton>
				{/if}
				{#if onremove}
					<IconButton label={m.rule_remove()} onclick={onremove}>
						<Trash2 aria-hidden="true" />
					</IconButton>
				{/if}
			</div>
		{/if}
	</div>
	{#if error}<Field.Error>{error}</Field.Error>{/if}
</div>
