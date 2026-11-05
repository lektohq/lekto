<script lang="ts" generics="C extends TreeCondition">
	import ConditionTree from '#lib/components/rules/ConditionTree.svelte';
	import { groupHeading, type TreeCondition, type TreeGroup } from '#lib/rules/tree.ts';

	// The conditions of a rule of any kind to read (a rule's page, a version): each group with
	// its heading ("Alle davon", "Keine davon"), its items indented under it. The kind says a
	// condition in words (`describe`).
	let { group, describe }: { group: TreeGroup<C>; describe: (condition: C) => string } = $props();
</script>

<div class="flex flex-col gap-1.5">
	<span class="text-sm text-muted-foreground">{groupHeading(group)}</span>
	<ul class="flex flex-col gap-1.5 border-l-2 pl-3">
		{#each group.items as item (item.key)}
			<li>
				{#if item.kind === 'group'}
					<ConditionTree group={item as TreeGroup<C>} {describe} />
				{:else}
					{describe(item as C)}
				{/if}
			</li>
		{/each}
	</ul>
</div>
