<script lang="ts" module>
	/** A tall editor with parts keeps this height whatever part shows (a contact's, an account's). */
	export const TALL = 'h-[min(53.75rem,calc(100dvh-2rem))]';
	/** The height of `fixed`. */
	const FIXED = 'h-[min(46.25rem,calc(100dvh-2rem))]';
</script>

<script lang="ts">
	import PhoneEditorBar, { FULL_SCREEN } from '#lib/components/PhoneEditorBar.svelte';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import type { Snippet } from 'svelte';
	import AsyncForm from '#lib/components/AsyncForm.svelte';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import Segmented, { type Segment } from '#lib/components/Segmented.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { cn } from '#lib/utils.ts';

	// The frame of a master data editor: a form in a dialog whose body scrolls while its title
	// and its footer (delete, cancel, save) stay; on a phone a sheet over the whole screen with a
	// fixed bar on top ("Cancel" · title · "Save") and deleting at the end of the body. Saving
	// runs `action`: the editor is busy meanwhile, closes when it resolves and shows the error
	// above the body when it throws. Deleting asks first (`ondelete`, only for an item that
	// exists). A long editor has `tabs` under its
	// title (Tobi, 20.10.2026): the caller shows the part of `tab`, the body starts at its top
	// again, and the dialog keeps one height (`class`, `TALL`), on a phone they share its width.
	// Without `action` it saves nothing of its own (the account dialog, whose parts each save
	// themselves): no form around the body, no footer, "Fertig" in the phone's bar. An editor of
	// several steps (web/DESIGN.md, "Dialogs"): the submit of a step before the last leads on
	// (`stay`: it does not close), and a later step has `back`: "Zurück" at the start of the
	// footer, on a phone instead of "Abbrechen" in the bar. An editor whose body is a field of
	// things to work on (the pages of "PDF bearbeiten") keeps its tools in place: `top` stands
	// fixed under the title, `bottom` fixed under the body, and only the body scrolls;
	// `footNote` says at the start of the footer how it is worked (the keyboard).
	let {
		open = $bindable(false),
		title,
		shortTitle = title,
		description,
		submitLabel = '',
		disabled = false,
		action,
		ondelete,
		deleteTitle = '',
		deleteDescription = '',
		class: className,
		size = 'lg',
		fixed = false,
		tabs,
		tab = $bindable(''),
		stay = false,
		back,
		shortSubmitLabel,
		top,
		bottom,
		footNote,
		children: body
	}: {
		open?: boolean;
		title: string;
		/** The title in the phone's bar: what is edited ("Contact"), not its name. */
		shortTitle?: string;
		description?: string;
		submitLabel?: string;
		/** Saving is not possible yet (a name is missing). */
		disabled?: boolean;
		action?: () => Promise<void>;
		ondelete?: () => Promise<void>;
		deleteTitle?: string;
		deleteDescription?: string;
		/** The height of the dialog with tabs. */
		class?: string;
		/** One height whatever part shows (web/DESIGN.md, "Dialogs": a dialog with parts keeps one height). */
		fixed?: boolean;
		/** The width of the dialog (`Dialog.Content`). */
		size?: 'md' | 'lg' | 'xl';
		tabs?: readonly Segment[];
		tab?: string;
		/** The submit leads to the next step: the editor stays open. */
		stay?: boolean;
		/** Back to the step before ("Zurück"). */
		back?: () => void;
		/** The submit in the phone's bar, a short verb ("Weiter"); default "Speichern". */
		shortSubmitLabel?: string;
		/** Fixed under the title: tools, the parts of a selection. */
		top?: Snippet;
		/** Fixed under the body (a phone's selection bar). */
		bottom?: Snippet;
		/** At the start of the desktop footer, muted: how the body is worked. */
		footNote?: string;
		children: Snippet;
	} = $props();

	let confirming = $state(false);
	let staying = false;
	let scroller = $state<HTMLElement | null>(null);

	$effect(() => {
		void tab;
		if (scroller) scroller.scrollTop = 0;
	});
</script>

{#snippet frame(busy: boolean, error: string | null)}
	{#if phone.current}
		<PhoneEditorBar
			title={shortTitle}
			submitLabel={action ? (shortSubmitLabel ?? m.editor_save_short()) : undefined}
			disabled={busy || disabled}
			cancelLabel={back ? m.editor_back() : undefined}
			oncancel={back ?? (() => (open = false))}
		/>
	{:else}
		<Dialog.Header class="shrink-0 px-4 pt-4 pr-12 pb-3">
			<Dialog.Title>{title}</Dialog.Title>
			{#if description}<Dialog.Description>{description}</Dialog.Description>{/if}
		</Dialog.Header>
	{/if}
	{#if tabs}
		<div class={cn('shrink-0 px-4 pb-3', phone.current && 'pt-3')}>
			<Segmented
				bind:value={tab}
				options={tabs}
				label={title}
				equal={phone.current}
				class={phone.current ? 'w-full' : ''}
			/>
		</div>
	{/if}
	{#if error}
		<p class="shrink-0 border-b bg-destructive/5 px-4 py-2 text-sm text-destructive" role="alert">
			{error}
		</p>
	{/if}
	{#if top}
		<div
			class={cn('flex shrink-0 flex-col gap-3 border-b bg-card px-4 pb-3', phone.current && 'pt-3')}
		>
			{@render top()}
		</div>
	{/if}
	<div
		bind:this={scroller}
		class={cn(
			'flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain px-4 pb-4',
			((phone.current && !tabs) || top) && 'pt-4',
			top && 'bg-background'
		)}
	>
		{#if phone.current && description}
			<p class="text-sm text-muted-foreground">{description}</p>
		{/if}
		{@render body()}
		{#if phone.current && ondelete}
			<Button
				type="button"
				variant="outline"
				class="mt-2 text-destructive"
				onclick={() => (confirming = true)}
			>
				<Trash2 aria-hidden="true" />
				{deleteTitle}
			</Button>
		{/if}
	</div>
	{#if bottom}
		<div class="shrink-0">{@render bottom()}</div>
	{/if}
	{#if !phone.current && action}
		<div class="flex shrink-0 flex-wrap items-center gap-2 border-t bg-muted/50 p-4">
			{#if footNote}
				<p class="min-w-0 flex-1 text-meta text-muted-foreground">{footNote}</p>
			{/if}
			{#if back}
				<Button type="button" variant="ghost" disabled={busy} onclick={back}>
					{m.editor_back()}
				</Button>
			{/if}
			{#if ondelete}
				<Button
					type="button"
					variant="ghost"
					class="text-destructive hover:text-destructive"
					aria-label={deleteTitle}
					onclick={() => (confirming = true)}
				>
					<Trash2 aria-hidden="true" />
					{m.delete_title()}
				</Button>
			{/if}
			<div class="ml-auto flex gap-2">
				<Button type="button" variant="ghost" onclick={() => (open = false)}>
					{m.cancel()}
				</Button>
				<Button type="submit" disabled={busy || disabled}>{submitLabel}</Button>
			</div>
		</div>
	{/if}
{/snippet}

<Dialog.Root bind:open>
	<Dialog.Content
		{size}
		showCloseButton={!phone.current}
		class={cn(
			'flex flex-col gap-0 overflow-hidden p-0',
			phone.current ? FULL_SCREEN : cn('max-h-[calc(100dvh-2rem)]', fixed && FIXED, className)
		)}
	>
		{#if action}
			<AsyncForm
				class="flex min-h-0 flex-1 flex-col"
				action={async () => {
					// As it was when the step was submitted: the step may change meanwhile.
					staying = stay;
					await action?.();
				}}
				ondone={() => {
					if (!staying) open = false;
				}}
			>
				{#snippet children({ busy, error })}{@render frame(busy, error)}{/snippet}
			</AsyncForm>
		{:else}
			<div class="flex min-h-0 flex-1 flex-col">{@render frame(false, null)}</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>

{#if ondelete}
	<ConfirmDialog
		bind:open={confirming}
		title={deleteTitle}
		description={deleteDescription}
		confirmLabel={m.delete_title()}
		onconfirm={ondelete}
	/>
{/if}
