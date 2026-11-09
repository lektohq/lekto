<script lang="ts">
	import { setMode, userPrefersMode } from 'mode-watcher';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { THEME_OPTIONS, type Theme } from '#lib/theme.ts';

	// Light, dark or as the system, as a group of the theme menu. (On a phone the navigation sheet
	// holds them as pills instead; `AppShell`.) Follows the system until chosen; mode-watcher
	// keeps the choice in this browser.
</script>

<DropdownMenu.Group>
	<DropdownMenu.GroupHeading>{m.theme_label()}</DropdownMenu.GroupHeading>
	<DropdownMenu.RadioGroup
		value={userPrefersMode.current}
		onValueChange={(value) => setMode(value as Theme)}
	>
		{#each THEME_OPTIONS as choice (choice.value)}
			<DropdownMenu.RadioItem value={choice.value}>
				<choice.icon aria-hidden="true" />
				{choice.label()}
			</DropdownMenu.RadioItem>
		{/each}
	</DropdownMenu.RadioGroup>
</DropdownMenu.Group>
