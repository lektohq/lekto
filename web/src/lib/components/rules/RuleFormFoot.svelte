<script lang="ts">
	import { Button, buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The foot of the editor of a rule, a document's or a mail's (web/DESIGN.md, "Mail rules"):
	// what belongs to no block of the form, that saving leads into the dry run, "Abbrechen" (a
	// link back) and "Speichern und Probelauf". It stands in the editor's form and submits it.
	let {
		error,
		held,
		cancelHref,
		oncancel
	}: {
		/** The problem that belongs to no block. */
		error: string | null;
		/** Saving is on its way, or the form cannot be saved as it stands. */
		held: boolean;
		cancelHref: string;
		/** "Abbrechen" was chosen: the changes are dropped on purpose (no question on leaving). */
		oncancel?: () => void;
	} = $props();
</script>

<div class="flex flex-col gap-3 border-t pt-4">
	{#if error}<Field.Error>{error}</Field.Error>{/if}
	<p class="text-sm text-muted-foreground">{m.rule_save_hint()}</p>
	<div class="flex flex-wrap justify-end gap-2">
		<a href={cancelHref} class={cn(buttonVariants({ variant: 'ghost' }))} onclick={oncancel}>
			{m.cancel()}
		</a>
		<Button type="submit" disabled={held}>{m.rule_save()}</Button>
	</div>
</div>
