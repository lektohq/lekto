<script lang="ts">
	import ArrowDown from '@lucide/svelte/icons/arrow-down';
	import ArrowUp from '@lucide/svelte/icons/arrow-up';
	import ArrowUpDown from '@lucide/svelte/icons/arrow-up-down';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import IconButton from '#lib/components/IconButton.svelte';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The sort of the list as a compact menu: its face says by what and which way ("Document date
	// ↓"), on a phone only an icon; the menu lists every sort in full.
	let {
		options,
		value,
		short,
		onchange,
		compact = false,
		class: className
	}: {
		options: readonly { value: string; label: string }[];
		value: string;
		short: { key: string; direction: 'up' | 'down' | null };
		onchange: (value: string) => void;
		compact?: boolean;
		class?: string;
	} = $props();

	const current = $derived(options.find((option) => option.value === value)?.label ?? short.key);
</script>

<DropdownMenu.Root>
	{#if compact}
		<DropdownMenu.Trigger>
			{#snippet child({ props })}
				<IconButton
					{...props}
					variant="outline"
					class={className}
					label={m.sort_current({ label: current })}
				>
					<ArrowUpDown aria-hidden="true" />
				</IconButton>
			{/snippet}
		</DropdownMenu.Trigger>
	{:else}
		<DropdownMenu.Trigger
			class={cn(buttonVariants({ variant: 'outline' }), className)}
			aria-label={m.sort_current({ label: current })}
		>
			<span class="whitespace-nowrap">{short.key}</span>
			{#if short.direction === 'down'}
				<ArrowDown class="size-3.5 text-muted-foreground" aria-hidden="true" />
			{:else if short.direction === 'up'}
				<ArrowUp class="size-3.5 text-muted-foreground" aria-hidden="true" />
			{/if}
			<ChevronDown class="size-3.5 text-muted-foreground" aria-hidden="true" />
		</DropdownMenu.Trigger>
	{/if}
	<DropdownMenu.Content align="end" class="w-64">
		<DropdownMenu.Group>
			<DropdownMenu.GroupHeading>{m.sort_label()}</DropdownMenu.GroupHeading>
			<DropdownMenu.RadioGroup {value} onValueChange={onchange}>
				{#each options as option (option.value)}
					<DropdownMenu.RadioItem value={option.value}>{option.label}</DropdownMenu.RadioItem>
				{/each}
			</DropdownMenu.RadioGroup>
		</DropdownMenu.Group>
	</DropdownMenu.Content>
</DropdownMenu.Root>
