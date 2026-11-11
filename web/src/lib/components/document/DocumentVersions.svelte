<script lang="ts">
	import Download from '@lucide/svelte/icons/download';
	import type { components } from '#lib/api/schema.ts';
	import VersionUpload from '#lib/components/document/VersionUpload.svelte';
	import { documentApi } from '#lib/document-view.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { formatMoment, listLocale, quoted } from '#lib/i18n.ts';
	import { userName, type Lookup } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	type Version = components['schemas']['DocumentVersionOut'];

	// The versions of a document's original (web/DESIGN.md, Glossary "Fassung"): the current
	// one marked, each with how and when it came and by whom, and its file to download. None is
	// ever overwritten. An editor puts a new version in the place of the current one ("Neue
	// Fassung hochladen", `POST /documents/{id}/versions`): processing runs again, keeps what a
	// person confirmed, and the document waits in the inbox. A merge says what it was merged
	// from ("Zusammengeführt aus Fassung 1 und „scan_0412“"), and a version that came along from a
	// merged document says from where ("Aus „scan_0412“ (dort Fassung 1)") before how it came.
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

	let upload = $state<ReturnType<typeof VersionUpload> | null>(null);

	const how = (version: Version) => {
		const moved = movedFrom(version.detail.moved);
		return moved ? `${moved} · ${kind(version)}` : kind(version);
	};

	const kind = (version: Version) => {
		if (version.kind === 'merged') return m.version_merged({ sources: sourcesOf(version) });
		if (version.kind === 'replaced') return m.version_replaced();
		if (version.kind === 'edited')
			return m.version_edited({ from: String(version.detail.from ?? '') });
		if (version.kind === 'split')
			return m.version_split({ title: String(version.detail.title ?? '') });
		if (version.kind === 'separated')
			return m.version_separated({
				pages: pagesOf(version.detail.pages),
				from: String(version.detail.from ?? '')
			});
		return m.version_received();
	};

	/** The pages a version was made of, of one source: "S. 1–3" (a part of a stack is a run). */
	function pagesOf(picks: unknown): string {
		const pages = Array.isArray(picks)
			? picks.map((pick) => Number((pick as { page?: unknown }).page)).filter(Number.isFinite)
			: [];
		if (pages.length === 0) return '';
		const first = String(Math.min(...pages));
		const last = String(Math.max(...pages));
		return first === last
			? m.page_edit_part_page({ page: first })
			: m.page_edit_part_pages({ first, last });
	}

	/** Where a version taken over in a merge came from, or null. */
	function movedFrom(moved: unknown): string | null {
		if (typeof moved !== 'object' || moved === null) return null;
		const { title, version } = moved as { title?: unknown; version?: unknown };
		return m.version_moved({ title: String(title ?? ''), version: String(version ?? '') });
	}

	/** The documents a merge was made of: this one by its version, the others by title. */
	function sourcesOf(version: Version): string {
		const merged = Array.isArray(version.detail.documents) ? version.detail.documents : [];
		const names = merged.map((item) => {
			const { document, title, version: number } = item as Record<string, unknown>;
			return document === documentId
				? m.version_merged_self({ version: String(number ?? '') })
				: quoted(String(title ?? ''));
		});
		return new Intl.ListFormat(listLocale(), { type: 'conjunction' }).format(names);
	}

	function download(number: number) {
		const link = window.document.createElement('a');
		link.href = `${documentApi(documentId)}/versions/${number}/original`;
		link.download = '';
		link.click();
	}
</script>

<Card.Root as="section" size="row" aria-labelledby="files-versions" class="flex flex-col gap-1">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<SectionTitle size="card" id="files-versions">{m.files_versions()}</SectionTitle>
		{#if editable}
			<Button variant="secondary" size="sm" onclick={() => upload?.start()}>
				{m.version_upload()}
			</Button>
			<VersionUpload
				bind:this={upload}
				{documentId}
				{title}
				current={versions.at(-1)?.number ?? 1}
				{onchanged}
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
