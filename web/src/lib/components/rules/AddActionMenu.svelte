<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// "Aktion hinzufügen" of the editor of a rule, a document's or a mail's (web/DESIGN.md,
	// "Mail rules"): added like a condition, a button, here with the kinds of action in its
	// menu, in groups where the rule has them (a mail rule's steps on the server come after
	// what it takes, under their own heading).
	let {
		groups,
		disabled = false
	}: {
		groups: readonly {
			/** The heading of the group; the first has none. */
			label?: string;
			items: readonly { key: string; label: string; onselect: () => void }[];
		}[];
		/** No further action fits. */
		disabled?: boolean;
	} = $props();

	const shown = $derived(groups.filter((group) => group.items.length > 0));
</script>

<div>
	<DropdownMenu.Root>
		<DropdownMenu.Trigger
			data-row="add"
			class={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
			{disabled}
		>
			<Plus aria-hidden="true" />
			{m.rule_add_action()}
		</DropdownMenu.Trigger>
		<DropdownMenu.Content align="start" class="w-64">
			{#each shown as group, index (index)}
				{#if index > 0}<DropdownMenu.Separator />{/if}
				{#if group.label}<DropdownMenu.Label>{group.label}</DropdownMenu.Label>{/if}
				{#each group.items as item (item.key)}
					<DropdownMenu.Item onSelect={item.onselect}>{item.label}</DropdownMenu.Item>
				{/each}
			{/each}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
</div>
