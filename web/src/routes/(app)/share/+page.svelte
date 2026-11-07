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
	import { reportError } from '#lib/errors.ts';
	import { intakeOf } from '#lib/intake.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { takeShared } from '#lib/shared-files.ts';
	import { uploads } from '#lib/upload.svelte.ts';

	// Files another app shared with the installed one (web/DESIGN.md, "App"): they go the way of
	// an upload, into the personal space, and the inbox shows what came of them. The share's id
	// stands in the address only until the files are taken.
	let missing = $state(false);

	onMount(async () => {
		const id = page.url.searchParams.get('id');
		let files: File[] = [];
		try {
			files = isShareId(id) ? await takeShared(id) : [];
		} catch (error) {
			reportError(error);
		}
		if (files.length) {
			uploads.add(intakeOf(files));
			await goto(`${BASE}/inbox`, { replaceState: true });
		} else {
			missing = true;
			await goto(`${BASE}/share`, { replaceState: true });
		}
	});
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
	{:else}
		<Loading />
	{/if}
</div>
