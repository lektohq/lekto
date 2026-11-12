<script lang="ts">
	import ArrowRight from '@lucide/svelte/icons/arrow-right';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import type { Component, Snippet } from 'svelte';
	import * as Card from '#lib/components/ui/card/index.ts';

	// A tile of the overview (Tobi, 27.10.2026): what a place holds that waits for someone, under
	// its name and icon, and the way there at the foot. On a phone, two to a row, the whole tile
	// is the way there with a chevron in its head (Tobi, 12.11.2026): the link takes the tile, its
	// words for screen readers only; a control inside stands above it (`relative z-10`).
	let {
		title,
		icon: Icon,
		href,
		go,
		children
	}: {
		title: string;
		icon: Component;
		href: string;
		/** The way there, a verb phrase ("Zum Posteingang"). */
		go: string;
		children: Snippet;
	} = $props();
</script>

<Card.Root
	as="section"
	class="relative flex flex-col gap-3 max-sm:gap-2 max-sm:p-4"
	aria-label={title}
>
	<div class="flex items-center gap-2 text-muted-foreground">
		<Icon class="size-4 shrink-0" aria-hidden="true" />
		<Card.Title class="min-w-0 truncate text-foreground">{title}</Card.Title>
		<ChevronRight class="ms-auto size-4 shrink-0 sm:hidden" aria-hidden="true" />
	</div>
	{@render children()}
	<a
		{href}
		class="mt-auto inline-flex min-h-8 items-center gap-1.5 self-start font-medium text-brand hover:underline max-sm:absolute max-sm:inset-0 max-sm:mt-0 max-sm:self-stretch max-sm:rounded-2xl"
	>
		<span class="max-sm:sr-only">{go}</span>
		<ArrowRight class="size-4 max-sm:hidden" aria-hidden="true" />
	</a>
</Card.Root>
