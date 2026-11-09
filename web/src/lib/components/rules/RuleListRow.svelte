<script lang="ts">
	import type { Snippet } from 'svelte';
	import EditButton from '#lib/components/EditButton.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import RuleSwitch from '#lib/components/rules/RuleSwitch.svelte';
	import { m } from '#lib/paraglide/messages.js';

	// The row of a rule in a list, the same for document and mail rules (web/DESIGN.md, "Lists",
	// "Mail rules"): the name's link takes the whole row, badges beside it, the summary below,
	// why Lekto paused it in `destructive`. The switch and the pencil stand above the link for
	// whoever may change the rule; the others see a badge of its state.
	let {
		href,
		editHref,
		name,
		enabled,
		disabledReason = null,
		canChange = true,
		busy = false,
		onswitch,
		badges,
		summary
	}: {
		href: string;
		editHref: string;
		name: string;
		enabled: boolean;
		disabledReason?: string | null;
		canChange?: boolean;
		busy?: boolean;
		onswitch: (enabled: boolean) => void;
		badges?: Snippet;
		summary: Snippet;
	} = $props();
</script>

<Card.Root as="li" size="row" class="relative flex flex-wrap items-center gap-3">
	<div class="flex min-w-0 flex-1 flex-col gap-1">
		<span class="flex flex-wrap items-center gap-2">
			<a
				{href}
				class="truncate font-medium after:absolute after:inset-0 hover:underline"
				aria-label={m.rule_open({ name })}>{name}</a
			>
			{@render badges?.()}
		</span>
		<span class="text-sm text-muted-foreground">{@render summary()}</span>
		{#if disabledReason}
			<span class="text-sm text-destructive"
				>{m.rule_disabled_reason({ reason: disabledReason })}</span
			>
		{/if}
	</div>
	{#if canChange}
		<RuleSwitch {name} {enabled} {busy} {onswitch} class="relative z-10" />
		<EditButton class="relative z-10" label={m.rule_edit_title({ name })} href={editHref} />
	{:else}
		<Badge variant={enabled ? 'green' : 'muted'}>{enabled ? m.rule_on() : m.rule_off()}</Badge>
	{/if}
</Card.Root>
