<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { components } from '#lib/api/schema.ts';
	import PageImages from '#lib/components/document/PageImages.svelte';
	import PdfViewer from '#lib/components/PdfViewer.svelte';
	import {
		hasArchive,
		pageImageHref,
		viewerSources,
		type Mark,
		type Place
	} from '#lib/document-view.ts';
	import type { Layout } from '#lib/viewer/zoom.ts';

	// A document's pages, the one way the document view and the Beam show them (Tobi, 03.11.2026):
	// the archive PDF once it exists; until then the page images (they come early, while the text
	// is still being recognised), and before those are rendered the original PDF. `marks` belong
	// to the archive, so they stand on it only, not on the images of the original. Anew once the
	// archive exists.
	let {
		document,
		label,
		marks = [],
		start = null,
		end,
		onpage
	}: {
		document: Pick<
			components['schemas']['DocumentDetails'],
			'id' | 'media_type' | 'page_count' | 'processing'
		>;
		label: string;
		marks?: readonly Mark[];
		/** How the viewer starts (`PageViewer`). */
		start?: Layout | null;
		/** At the end of the toolbar (the switch of a pane). */
		end?: Snippet;
		/** The page in the upper third of the view, and how many there are. */
		onpage?: (current: number, total: number) => void;
	} = $props();

	const archive = $derived(hasArchive(document));
	let pdf = $state<PdfViewer | null>(null);

	/** Scroll so that `place` (on the archive) stands in the upper third of the view. */
	export function reveal(place: Place) {
		pdf?.reveal(place);
	}
</script>

{#key `${document.id}:${archive}`}
	{#if archive || !document.page_count}
		<PdfViewer
			bind:this={pdf}
			sources={viewerSources(document, archive)}
			{label}
			marks={archive ? marks : []}
			{start}
			{end}
			{onpage}
		/>
	{:else}
		<PageImages
			pages={Array.from({ length: document.page_count }, (_, index) => ({
				src: pageImageHref(document.id, index + 1)
			}))}
			{label}
			{start}
			{end}
			{onpage}
		/>
	{/if}
{/key}
