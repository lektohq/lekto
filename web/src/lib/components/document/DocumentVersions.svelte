<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { apiError } from '#lib/api/problem.ts';
	import type { components } from '#lib/api/schema.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import { documentApi } from '#lib/document-view.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { formatMoment } from '#lib/i18n.ts';
	import { userName, type Lookup } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Version = components['schemas']['DocumentVersionOut'];

	// The versions of a document's original (web/DESIGN.md, Glossary "Fassung"): the current
	// one marked, each with how and when it came and by whom, and its file to download. None is
	// ever overwritten. An editor puts a new version in the place of the current one ("Neue
	// Fassung hochladen", `POST /documents/{id}/versions`): processing runs again, keeps what a
	// person confirmed, and the document waits in the inbox.
	let {
		documentId,
		title,
		versions,
		lookup,
		editable = false,
		onchanged
	}: {
		documentId: string;
		/** The document's title, named when its file is replaced. */
		title: string;
		versions: readonly Version[];
		lookup: Lookup | null;
		editable?: boolean;
		/** After a new version was uploaded. */
		onchanged?: () => void;
	} = $props();

	let picker = $state<HTMLInputElement | null>(null);
	let chosen = $state<File | null>(null);
	let asking = $state(false);

	const how = (version: Version) => {
		if (version.kind === 'replaced') return m.version_replaced();
		if (version.kind === 'edited')
			return m.version_edited({ from: String(version.detail.from ?? '') });
		return m.version_received();
	};

	function download(number: number) {
		const link = window.document.createElement('a');
		link.href = `${documentApi(documentId)}/versions/${number}/original`;
		link.download = '';
		link.click();
	}

	async function replace() {
		const file = chosen;
		if (!file) return;
		const form = new FormData();
		form.append('file', file, file.name);
		const { data, error, response } = await api.POST('/api/v1/documents/{id}/versions', {
			params: { path: { id: documentId } },
			// The generated type wants a string for the file; the form carries the binary.
			body: { file: '' },
			bodySerializer: () => form
		});
		if (!data) throw await apiError(response, error);
		toast.success(m.version_replaced_done());
		onchanged?.();
	}
</script>

<Card.Root as="section" size="row" aria-labelledby="files-versions" class="flex flex-col gap-1">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<SectionTitle size="card" id="files-versions">{m.files_versions()}</SectionTitle>
		{#if editable}
			<Button variant="secondary" size="sm" onclick={() => picker?.click()}>
				{m.version_upload()}
			</Button>
			<input
				bind:this={picker}
				type="file"
				accept="application/pdf,image/jpeg,image/png,image/tiff"
				class="hidden"
				aria-hidden="true"
				tabindex="-1"
				onchange={(event) => {
					chosen = event.currentTarget.files?.[0] ?? null;
					asking = chosen !== null;
					event.currentTarget.value = '';
				}}
			/>
		{/if}
	</div>
	<ol class="flex flex-col">
		{#each [...versions].reverse() as version (version.number)}
			<li class="flex items-center gap-3 border-t py-2.5 first:border-t-0">
				<div class="flex min-w-0 flex-1 flex-col gap-0.5">
					<span class="flex flex-wrap items-center gap-2 text-sm font-medium">
						{m.version_number({ number: String(version.number) })}
						{#if version.current}<Badge variant="primary">{m.version_current()}</Badge>{/if}
					</span>
					<span class="text-sm break-words text-muted-foreground">
						{[
							how(version),
							version.created_by ? userName(lookup?.users ?? [], version.created_by) : null,
							formatMoment(version.created_at),
							version.original_filename
						]
							.filter(Boolean)
							.join(' · ')}
					</span>
				</div>
				<Button variant="ghost" size="sm" onclick={() => download(version.number)}>
					<Download aria-hidden="true" />
					{m.doc_download()}
				</Button>
			</li>
		{/each}
	</ol>
</Card.Root>

<!-- The current file stays as a version: nothing is lost, so no destructive look. -->
<ConfirmDialog
	bind:open={asking}
	destructive={false}
	title={m.version_replace_title({ title, file: chosen?.name ?? '' })}
	description={m.version_replace_text({ number: String(versions.at(-1)?.number ?? 1) })}
	confirmLabel={m.version_replace()}
	onconfirm={replace}
/>
