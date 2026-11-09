<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';
	import InfoTip from '#lib/components/InfoTip.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The title of a section of a page (`section`, `text-lg`) or of a card or pane (`card`,
	// `text-md`), web/DESIGN.md, "Typography". The level follows the outline of the page, not the
	// look: a card's title on a page is an `<h2>`, inside a section an `<h3>`. With `tip` the help
	// of the section stands beside it (web/DESIGN.md, "Help and tooltips"), named by `tip.name`.
	let {
		level = 2,
		size = 'section',
		tip,
		class: className,
		children,
		...rest
	}: HTMLAttributes<HTMLHeadingElement> & {
		level?: 2 | 3 | 4;
		size?: 'section' | 'card';
		tip?: { name: string; text: string };
		children: Snippet;
	} = $props();
</script>

{#snippet title()}
	<svelte:element
		this={`h${level}`}
		class={cn('font-semibold', size === 'section' ? 'text-lg' : 'text-md leading-tight', className)}
		{...rest}
	>
		{@render children()}
	</svelte:element>
{/snippet}

{#if tip}
	<div class="flex items-center gap-1">
		{@render title()}
		<InfoTip label={m.hint_about({ name: tip.name })} size="sm" class="w-80">
			<p>{tip.text}</p>
		</InfoTip>
	</div>
{:else}
	{@render title()}
{/if}
