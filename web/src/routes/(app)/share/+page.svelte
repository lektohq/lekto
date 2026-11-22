<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { isShareId } from '#lib/app-cache.ts';
	import { BASE } from '#lib/base.ts';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { fileSize } from '#lib/file-passport.ts';
	import { intakeOf } from '#lib/intake.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { forgetShared, forgetSharedFile, readShared } from '#lib/shared-files.ts';
	import { uploads } from '#lib/upload.svelte.ts';

	// Files another app shared with the installed one (web/DESIGN.md, "App"). Any website can post
	// files to the share target, with no click of the person, so nothing is uploaded here by
	// itself: the page shows the files, and only "Hochladen" hands them to the upload (into the
	// personal space; the inbox shows what came of them). The share's id stands in the address
	// until the person has decided. A file stays on the device until its upload has a result;
	// one that failed stays, and the inbox's list leads back here to try again.

	/** How long the page must have been in front before "Hochladen" counts: a website that asks
	 * for a double click and brings this page up between the two must not get the second one. */
	const HELD_FOR_MS = 1000;

	let id: string | null = null;
	let files = $state<File[] | null>(null);
	let missing = $state(false);
	let held = $state(true);
	let decided = false;

	onMount(() => {
		let timer: ReturnType<typeof setTimeout> | undefined;
		const hold = () => {
			held = true;
			clearTimeout(timer);
		};
		const release = () => {
			hold();
			timer = setTimeout(() => (held = false), HELD_FOR_MS);
		};
		const seen = () => (document.visibilityState === 'visible' ? release() : hold());
		window.addEventListener('focus', release);
		window.addEventListener('blur', hold);
		document.addEventListener('visibilitychange', seen);
		void show().then(release);
		return () => {
			clearTimeout(timer);
			window.removeEventListener('focus', release);
			window.removeEventListener('blur', hold);
			document.removeEventListener('visibilitychange', seen);
		};
	});

	async function show() {
		const given = page.url.searchParams.get('id');
		let found: File[] = [];
		try {
			found = isShareId(given) ? await readShared(given) : [];
		} catch (error) {
			reportError(error);
		}
		if (found.length && isShareId(given)) {
			id = given;
			files = found;
		} else {
			missing = true;
			await goto(`${BASE}/share`, { replaceState: true });
		}
	}

	/** The share leaves the device, and the inbox is next: the person discarded it. */
	async function leave() {
		try {
			if (id) await forgetShared(id);
		} catch (error) {
			reportError(error);
		}
		await goto(`${BASE}/inbox`, { replaceState: true });
	}

	/** A file's upload has a result: it leaves the device. */
	const drop = (file: File) => void forgetSharedFile(file).catch(reportError);

	async function upload() {
		if (held || decided || !files || !id) return;
		decided = true;
		const taken = intakeOf(files);
		// What the upload does not take (another type, hidden) has its result already.
		const sent = new Set(taken.files.map((entry) => entry.file));
		for (const file of files) if (!sent.has(file)) drop(file);
		uploads.add(taken, {
			settled: (file, state) => {
				if (state !== 'failed') drop(file);
			},
			again: `${BASE}/share?id=${id}`
		});
		await goto(`${BASE}/inbox`, { replaceState: true });
	}

	async function discard() {
		if (decided) return;
		decided = true;
		await leave();
	}
</script>

<svelte:head><title>{m.share_title()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.share_title()} />
	{#if missing}
		<EmptyNote>
			{m.share_missing()}
			{#snippet action()}
				<Button variant="outline" href={`${BASE}/inbox`}>{m.share_to_inbox()}</Button>
			{/snippet}
		</EmptyNote>
	{:else if files}
		<Card.Root as="section" class="flex flex-col gap-4" aria-label={m.share_files()}>
			<p class="text-sm text-muted-foreground">{m.share_hint()}</p>
			<ul class="flex flex-col divide-y">
				{#each files as file, index (index)}
					<li class="flex items-baseline gap-3 py-2">
						<span class="min-w-0 flex-1 wrap-anywhere">{file.name}</span>
						<span class="shrink-0 text-sm text-muted-foreground">{fileSize(file.size)}</span>
					</li>
				{/each}
			</ul>
			<div class="flex justify-end gap-2">
				<Button variant="ghost" onclick={discard}>{m.share_discard()}</Button>
				<Button aria-disabled={held} onclick={upload}>
					{m.upload_title()}
				</Button>
			</div>
		</Card.Root>
	{:else}
		<Loading />
	{/if}
</div>
