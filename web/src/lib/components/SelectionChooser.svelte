<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ListChecks from '@lucide/svelte/icons/list-checks';
	import type { Snippet } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	// "Auswählen" of a selection bar (web/DESIGN.md, "Choosing many"): a menu of what to choose at
	// once (`children`, its items: a page, every hit, none), before the count on a desktop, after
	// it on a phone. Always there, so that nothing moves as the choice changes.
	let { disabled = false, children }: { disabled?: boolean; children: Snippet } = $props();
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger {disabled}>
		{#snippet child({ props })}
			<Button {...props} variant="outline" size="sm">
				<ListChecks aria-hidden="true" />
				{m.bulk_mode()}
				<ChevronDown aria-hidden="true" />
			</Button>
		{/snippet}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align={phone.current ? 'end' : 'start'} class="w-64">
		{@render children()}
	</DropdownMenu.Content>
</DropdownMenu.Root>
