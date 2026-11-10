<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import type { components } from '#lib/api/schema.ts';
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
	// ever overwritten; a new one comes in when a person replaces the file or edits the pages.
	let {
		documentId,
		versions,
		lookup
	}: { documentId: string; versions: readonly Version[]; lookup: Lookup | null } = $props();

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
</script>

<Card.Root as="section" size="row" aria-labelledby="files-versions" class="flex flex-col gap-1">
	<SectionTitle size="card" id="files-versions">{m.files_versions()}</SectionTitle>
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
