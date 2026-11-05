<script lang="ts">
	import type CircleCheck from '@lucide/svelte/icons/circle-check';
	import type { ComponentProps } from 'svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';

	// A state as a badge in its tone, with its icon where it has one and its word
	// (web/DESIGN.md, "Badges": state is never colour alone; a plain fact such as "not fetched
	// yet" has no icon).
	let {
		tone,
		label,
		icon: Icon,
		size = 'sm',
		class: className = ''
	}: {
		tone: ComponentProps<typeof Badge>['variant'];
		label: string;
		icon?: typeof CircleCheck;
		size?: ComponentProps<typeof Badge>['size'];
		class?: string;
	} = $props();
</script>

<Badge variant={tone} {size} class={className}>
	{#if Icon}<Icon aria-hidden="true" strokeWidth={2.2} />{/if}
	{label}
</Badge>
