<script lang="ts">
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The page shows other filters, words or another sort than the open lens: keep them in it,
	// make a new lens of them, or go back to the lens.
	let {
		name,
		busy = false,
		onsave,
		onsaveas,
		ondiscard
	}: {
		name: string;
		busy?: boolean;
		onsave: () => void;
		onsaveas: () => void;
		ondiscard: () => void;
	} = $props();
</script>

<Alert.Root variant="warning" role="status" class="flex flex-wrap items-center gap-x-3 gap-y-2">
	<Alert.Description class="min-w-0 flex-1">{m.lens_changed()}</Alert.Description>
	<div class="flex flex-wrap gap-2">
		<Button variant="ghost" size="sm" disabled={busy} onclick={ondiscard}>
			{m.lens_discard()}
		</Button>
		<Button variant="outline" size="sm" disabled={busy} onclick={onsaveas}>
			{m.lens_save_as()}
		</Button>
		<Button size="sm" disabled={busy} onclick={onsave}>
			{m.lens_save_into({ name })}
		</Button>
	</div>
</Alert.Root>
