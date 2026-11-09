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
	// again, and the dialog keeps one height (`class`), on a phone they share its width.
	let {
		open = $bindable(false),
		title,
		shortTitle = title,
		description,
		submitLabel,
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
		children: body
	}: {
		open?: boolean;
		title: string;
		/** The title in the phone's bar: what is edited ("Contact"), not its name. */
		shortTitle?: string;
		description?: string;
		submitLabel: string;
		/** Saving is not possible yet (a name is missing). */
		disabled?: boolean;
		action: () => Promise<void>;
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
		children: Snippet;
	} = $props();

	let confirming = $state(false);
	let scroller = $state<HTMLElement | null>(null);

	$effect(() => {
		void tab;
		if (scroller) scroller.scrollTop = 0;
	});
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		{size}
		showCloseButton={!phone.current}
		class={cn(
			'flex flex-col gap-0 overflow-hidden p-0',
			phone.current
				? FULL_SCREEN
				: cn('max-h-[calc(100dvh-2rem)]', fixed && 'h-[min(46.25rem,calc(100dvh-2rem))]', className)
		)}
	>
		<AsyncForm class="flex min-h-0 flex-1 flex-col" {action} ondone={() => (open = false)}>
			{#snippet children({ busy, error })}
				{#if phone.current}
					<PhoneEditorBar
						title={shortTitle}
						submitLabel={m.editor_save_short()}
						disabled={busy || disabled}
						oncancel={() => (open = false)}
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
					<p
						class="shrink-0 border-b bg-destructive/5 px-4 py-2 text-sm text-destructive"
						role="alert"
					>
						{error}
					</p>
				{/if}
				<div
					bind:this={scroller}
					class={cn(
						'flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain px-4 pb-4',
						phone.current && !tabs && 'pt-4'
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
				{#if !phone.current}
					<div class="flex shrink-0 flex-wrap items-center gap-2 border-t bg-muted/50 p-4">
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
		</AsyncForm>
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
