<script lang="ts" module>
	/** A dialog on a phone, the editor pattern (web/DESIGN.md, "Dialogs, sheets, editors"): the
	 * whole screen, the safe area kept free. */
	export const FULL_SCREEN =
		'top-0 left-0 h-dvh max-h-dvh w-full max-w-none translate-x-0 translate-y-0 gap-0 rounded-none border-0 bg-background p-0 pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]';
	/** A button of a phone's bar: plain words in the brand colour ("Fertig" of a picker too). */
	export const BAR_ACTION = 'px-3 text-base font-semibold text-brand';
</script>

<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The bar on top of an editor on a phone: "Abbrechen", the title, the submit of the form it
	// stands in (in red where it deletes or ends something). It stands inside `Dialog.Content`.
	let {
		title,
		submitLabel,
		disabled = false,
		destructive = false,
		oncancel
	}: {
		title: string;
		submitLabel: string;
		disabled?: boolean;
		destructive?: boolean;
		oncancel: () => void;
	} = $props();
</script>

<div class="grid h-14 shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-1 border-b bg-card px-1">
	<Button
		type="button"
		variant="ghost"
		class={cn(BAR_ACTION, 'justify-self-start font-normal')}
		onclick={oncancel}
	>
		{m.cancel()}
	</Button>
	<Dialog.Title class="max-w-[50vw] truncate text-base font-semibold">{title}</Dialog.Title>
	<Button
		type="submit"
		variant="ghost"
		class={cn(BAR_ACTION, 'justify-self-end', destructive && 'text-destructive')}
		{disabled}
	>
		{submitLabel}
	</Button>
</div>
