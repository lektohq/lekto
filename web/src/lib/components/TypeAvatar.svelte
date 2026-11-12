<script lang="ts">
	import Shapes from '@lucide/svelte/icons/shapes';
	import TypeIcon from '#lib/components/TypeIcon.svelte';
	import { cn } from '#lib/utils.ts';

	// A document type at the start of its row: its icon round on the ground of a contact's
	// initials, so that the row of a type looks as a contact's (Tobi, 12.11.2026); without an
	// icon the shapes every type has, muted. Decorative: the type's name is next to it.
	let { icon, class: className }: { icon: string | null | undefined; class?: string } = $props();
</script>

<span
	class={cn(
		'inline-grid size-8 shrink-0 place-items-center rounded-full bg-panel text-brand',
		className
	)}
	aria-hidden="true"
	data-type-avatar
>
	{#if icon}
		<TypeIcon {icon} class="size-4" />
	{:else}
		<Shapes class="size-4 text-muted-foreground" />
	{/if}
</span>
