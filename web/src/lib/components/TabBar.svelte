<script lang="ts" module>
	export interface Tab {
		/** Compared with `current`. */
		key: string;
		href: string;
		label: string;
		/** A number after the name (the documents in the tab); none when 0. */
		count?: number;
		/** A dot after the name, read out as this (something to look at there). */
		marker?: string;
	}
</script>

<script lang="ts">
	import AlertDot from '#lib/components/AlertDot.svelte';
	import SteadyText from '#lib/components/SteadyText.svelte';
	import { slidingPill } from '#lib/sliding-pill.ts';
	import { centre, sideways, SIDEWAYS_FADE } from '#lib/sideways.ts';
	import { cn } from '#lib/utils.ts';

	// The tabs of a page (inbox, document, master data, system), web/DESIGN.md "Tabs and
	// switches": links over a line, the current one underlined in the brand colour; the line
	// moves over when another is chosen (`sliding-pill.ts`). Unlike `Segmented` (a pill: how to
	// show something) they lead somewhere. Where they are wider than the room (a phone) they
	// scroll sideways in their own row, the current one in view, and the cut edge fades so that
	// it shows there is more; with `fill` they share a phone's width equally instead.
	let {
		label,
		tabs,
		current,
		fill = false,
		class: className = ''
	}: {
		label: string;
		tabs: readonly Tab[];
		current: string;
		fill?: boolean;
		class?: string;
	} = $props();

	let bar = $state<HTMLElement | null>(null);
	$effect(() => {
		void current;
		void tabs;
		centre(bar, '[aria-current="page"]');
	});
</script>

<nav
	bind:this={bar}
	{@attach slidingPill}
	{@attach sideways}
	aria-label={label}
	class={cn(
		'relative flex w-full max-w-full [scrollbar-width:none] gap-1 overflow-x-auto border-b',
		SIDEWAYS_FADE,
		fill && 'max-sm:grid max-sm:auto-cols-fr max-sm:grid-flow-col',
		className
	)}
>
	<span
		data-pill
		hidden
		aria-hidden="true"
		class="pointer-events-none absolute top-0 left-0 after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand data-moving:motion-safe:transition-[transform,width,height] data-moving:motion-safe:duration-300 data-moving:motion-safe:ease-out"
	></span>
	{#each tabs as tab (tab.key)}
		<a
			href={tab.href}
			aria-current={tab.key === current ? 'page' : undefined}
			class={cn(
				'relative inline-flex h-11 shrink-0 items-center justify-center gap-1.5 px-3 text-sm whitespace-nowrap transition-colors max-sm:min-w-11',
				fill && 'max-sm:px-1',
				tab.key === current
					? 'font-medium text-foreground'
					: 'text-muted-foreground hover:text-foreground'
			)}
		>
			<SteadyText text={tab.label} />
			{#if tab.count}
				<span class="text-xs font-normal text-muted-foreground tabular-nums">{tab.count}</span>
			{/if}
			{#if tab.marker}
				<AlertDot tone="yellow" label={tab.marker} />
			{/if}
		</a>
	{/each}
</nav>
