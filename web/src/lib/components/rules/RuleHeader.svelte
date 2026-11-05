<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Play from '@lucide/svelte/icons/play';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The head of a rule's page, the same for document and mail rules (web/DESIGN.md, "Mail
	// rules"): the switch, "Bearbeiten" and delete for whoever may change the rule, "Probelauf"
	// for whoever may apply it; below, the badges of the kind, the priority, why Lekto paused it,
	// and whatever else the kind adds (`extra`).
	let {
		title,
		back,
		rule,
		canChange = true,
		canApply = true,
		busy = false,
		editHref,
		applyHref,
		disabledReason = null,
		onswitch,
		ondelete,
		badges,
		extra
	}: {
		title: string;
		back: { href: string; label: string };
		rule: { name: string; enabled: boolean; priority: number } | null;
		canChange?: boolean;
		canApply?: boolean;
		busy?: boolean;
		editHref: string;
		applyHref: string;
		disabledReason?: string | null;
		onswitch: (enabled: boolean) => void;
		ondelete: () => void;
		badges?: Snippet;
		extra?: Snippet;
	} = $props();
</script>

<PageHeader {title} {back}>
	{#snippet actions()}
		{#if rule}
			{#if canChange}
				<Switch
					bind:checked={() => rule?.enabled ?? false, onswitch}
					disabled={busy}
					aria-label={rule.enabled
						? m.rule_switch_off({ name: rule.name })
						: m.rule_switch_on({ name: rule.name })}
				/>
				<a href={editHref} class={cn(buttonVariants({ variant: 'outline' }))}>
					<Pencil aria-hidden="true" />
					{m.rule_edit()}
				</a>
			{/if}
			{#if canApply}
				<a href={applyHref} class={cn(buttonVariants({ variant: 'outline' }))}>
					<Play aria-hidden="true" />
					{m.rule_dry_run()}
				</a>
			{/if}
			{#if canChange}
				<IconButton label={m.rule_delete({ name: rule.name })} onclick={ondelete}>
					<Trash2 aria-hidden="true" />
				</IconButton>
			{/if}
		{/if}
	{/snippet}
	{#snippet below()}
		{#if rule}
			<span class="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
				{@render badges?.()}
				{m.rule_priority_short({ priority: rule.priority })}
			</span>
			{#if disabledReason}
				<span class="text-sm text-destructive">
					{m.rule_disabled_reason({ reason: disabledReason })}
				</span>
			{/if}
			{@render extra?.()}
		{/if}
	{/snippet}
</PageHeader>
