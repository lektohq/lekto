<script lang="ts">
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import Download from '@lucide/svelte/icons/download';
	import Upload from '@lucide/svelte/icons/upload';
	import Zap from '@lucide/svelte/icons/zap';
	import { api } from '#lib/api/client.ts';
	import { BASE } from '#lib/base.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { appleDevice, install, isAndroid } from '#lib/install.svelte.ts';
	import { ACCEPT, intakeOf, readDrop, type Intake } from '#lib/intake.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';
	import { uploads } from '#lib/upload.svelte.ts';
	import { cn } from '#lib/utils.ts';

	// Upload into the personal space (Tobi, 21.10.2026: no choice of space; Lekto suggests where a
	// document belongs). Files are chosen (on a phone the system's picker offers the camera and the
	// photos) or dropped here, folders too; then the dialog closes and the inbox shows what came of
	// them.
	let { open = $bindable(false) }: { open?: boolean } = $props();

	let over = $state(false);
	// Android in the browser: the installed app is in the share sheet (web/DESIGN.md, "App").
	const offerInstall = $derived(install.available && isAndroid());
	// iPhone, iPad and Mac: the shortcut, if the server names one, until the person has a token
	// that only uploads.
	const apple = $derived(appleDevice() !== null && session.shortcutUrl !== null);
	let shortcutReady = $state(true);
	$effect(() => {
		if (!open || !apple) return;
		api.GET('/api/v1/auth/tokens').then(
			(answer) => (shortcutReady = answer.data?.some((token) => token.scope === 'upload') ?? true),
			() => (shortcutReady = true)
		);
	});
	let input = $state<HTMLInputElement | null>(null);

	function take(intake: Intake) {
		if (intake.files.length + intake.skipped.length === 0) return;
		uploads.add(intake);
		open = false;
	}

	function chosen() {
		if (input?.files) take(intakeOf(input.files));
		if (input) input.value = '';
	}

	function drop(event: DragEvent) {
		event.preventDefault();
		// The inbox page takes drops itself; this one is the dialog's.
		event.stopPropagation();
		over = false;
		if (event.dataTransfer) readDrop(event.dataTransfer).then(take, reportError);
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content size="lg">
		<Dialog.Header>
			<Dialog.Title>{m.upload_title()}</Dialog.Title>
			<Dialog.Description>{m.upload_hint()}</Dialog.Description>
		</Dialog.Header>

		<EmptyNote
			compact
			role="presentation"
			ondragover={(event) => {
				event.preventDefault();
				event.stopPropagation();
				over = true;
			}}
			ondragleave={() => (over = false)}
			ondrop={drop}
			class={cn('transition-colors', over && 'border-primary bg-secondary')}
		>
			{#snippet icon()}<Upload class="size-7" aria-hidden="true" />{/snippet}
			<span class="max-sm:hidden">{m.upload_drop()}</span>
			{#snippet action()}
				<Button variant="outline" onclick={() => input?.click()}>
					{m.upload_choose()}
				</Button>
			{/snippet}
			<input
				bind:this={input}
				type="file"
				multiple
				accept={ACCEPT}
				class="sr-only"
				tabindex="-1"
				aria-label={m.upload_choose()}
				onchange={chosen}
			/>
		</EmptyNote>
		{#if apple && !shortcutReady}
			<p class="flex items-center gap-2.5 border-t pt-4 text-sm text-muted-foreground">
				<Zap class="size-4 shrink-0" aria-hidden="true" />
				<span
					>{m.upload_share_hint()}
					<Button
						variant="link"
						size="inline"
						href={`${BASE}/settings?tab=tokens`}
						onclick={() => (open = false)}>{m.upload_set_up_shortcut()}</Button
					></span
				>
			</p>
		{:else if offerInstall}
			<p class="flex items-center gap-2.5 border-t pt-4 text-sm text-muted-foreground">
				<Download class="size-4 shrink-0" aria-hidden="true" />
				<span
					>{m.upload_share_hint()}
					<Button variant="link" size="inline" onclick={() => void install.ask()}
						>{m.upload_install_app()}</Button
					></span
				>
			</p>
		{/if}
	</Dialog.Content>
</Dialog.Root>
