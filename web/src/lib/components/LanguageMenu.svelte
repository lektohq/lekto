<script lang="ts">
	import Languages from '@lucide/svelte/icons/languages';
	import LanguageChoices from '#lib/components/LanguageChoices.svelte';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import { getLocale, LANGUAGE_NAMES } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	const current = getLocale();
	// What is read on the button comes first in its name: who steers by voice says "DE"
	// (WCAG 2.5.3).
	const shown = current.toUpperCase();
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		class={cn(
			buttonVariants({ variant: 'secondary', size: 'default' }),
			'max-[380px]:gap-1 max-[380px]:px-2.5'
		)}
		aria-label={`${shown}, ${m.language_label()}: ${LANGUAGE_NAMES[current]}`}
	>
		<Languages aria-hidden="true" />
		<span>{shown}</span>
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="end" class="w-44">
		<LanguageChoices />
	</DropdownMenu.Content>
</DropdownMenu.Root>
