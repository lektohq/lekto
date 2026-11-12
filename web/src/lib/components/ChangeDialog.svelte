<script lang="ts">
	import type { Snippet } from 'svelte';
	import AsyncForm from '#lib/components/AsyncForm.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// "Was die Änderung bewirkt" (web/DESIGN.md, "Change preview"): what a change would do, asked
	// before it takes effect (saving a document's form, applying "PDF bearbeiten"). A centred
	// dialog on a phone too: the description says nothing is stored yet, the body what follows
	// (`children`, scrolling), "Abbrechen" and the action. `action` runs on submit; the dialog is
	// busy meanwhile, closes when it resolves and stays open with the error when it throws.
	let {
		open = $bindable(false),
		description,
		submitLabel,
		destructive = false,
		action,
		children: body
	}: {
		open?: boolean;
		description: string;
		submitLabel: string;
		/** Where the change loses something (a document no part replaces). */
		destructive?: boolean;
		action: () => Promise<void>;
		children: Snippet;
	} = $props();
</script>

<Dialog.Root bind:open>
	<Dialog.Content size="md">
		<AsyncForm class="flex min-h-0 flex-col gap-4" {action} ondone={() => (open = false)}>
			{#snippet children({ busy, error })}
				<Dialog.Header>
					<Dialog.Title>{m.dryrun_title()}</Dialog.Title>
					<Dialog.Description>{description}</Dialog.Description>
				</Dialog.Header>
				<div class="max-h-[60vh] overflow-auto">{@render body()}</div>
				{#if error}<Field.Error>{error}</Field.Error>{/if}
				<Dialog.Footer>
					<Button type="button" variant="ghost" disabled={busy} onclick={() => (open = false)}>
						{m.cancel()}
					</Button>
					<Button type="submit" variant={destructive ? 'destructive' : 'default'} disabled={busy}>
						{submitLabel}
					</Button>
				</Dialog.Footer>
			{/snippet}
		</AsyncForm>
	</Dialog.Content>
</Dialog.Root>
