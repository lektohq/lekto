<script lang="ts">
	import X from '@lucide/svelte/icons/x';
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import PhoneSheet from '#lib/components/PhoneSheet.svelte';
	import * as Popover from '#lib/components/ui/popover/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { cn } from '#lib/utils.ts';

	// A choice from many by searching (web/DESIGN.md, "Dialogs"): what opens it (`trigger`, given
	// the props to spread), and the search with its list (`children`, a `Command`). A popover at the
	// trigger on wider screens; on a phone a sheet from the bottom (`PhoneSheet`) named `title`
	// with an X, where the list takes a finger's rows (`ui/command`).
	let {
		open = $bindable(false),
		title,
		onOpenChange,
		class: className,
		align = 'start',
		trigger,
		children
	}: {
		open?: boolean;
		/** The sheet's heading on a phone: "Kontakt wählen". */
		title: string;
		/** Hears of it closing (a choice does not: the caller closes it). */
		onOpenChange?: (open: boolean) => void;
		/** The popover's width. */
		class?: string;
		align?: 'start' | 'center' | 'end';
		trigger: Snippet<[Record<string, unknown>]>;
		children: Snippet;
	} = $props();
</script>

{#if phone.current}
	{@render trigger({
		'aria-haspopup': 'dialog',
		'aria-expanded': open,
		onclick: () => (open = true)
	})}
	<PhoneSheet bind:open {title} {onOpenChange}>
		{#snippet close()}
			<IconButton
				label={m.close()}
				onclick={() => {
					open = false;
					onOpenChange?.(false);
				}}
			>
				<X aria-hidden="true" />
			</IconButton>
		{/snippet}
		{@render children()}
	</PhoneSheet>
{:else}
	<Popover.Root bind:open {onOpenChange}>
		<Popover.Trigger>
			{#snippet child({ props })}
				{@render trigger(props)}
			{/snippet}
		</Popover.Trigger>
		<Popover.Content class={cn('p-0', className)} {align} collisionPadding={8}>
			{@render children()}
		</Popover.Content>
	</Popover.Root>
{/if}
