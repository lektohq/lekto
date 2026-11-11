<script lang="ts">
	import type { Snippet } from 'svelte';
	import PageViewer from '#lib/components/PageViewer.svelte';
	import PageImage from '#lib/components/pages/PageImage.svelte';
	import type { Place, ShownPage } from '#lib/document-view.ts';
	import { m } from '#lib/paraglide/messages.js';
	import type { Layout } from '#lib/viewer/zoom.ts';

	// Images of pages in the viewer of the PDF's: side by side, zoomed by gesture, each turned
	// as it is to be. A document's page images until its archive PDF exists (`DocumentPages`:
	// they come early, while the text is still being recognised), and the pages of an edit before
	// they are stored (the Beam, `showPages`). No marks, which belong to the archive.
	let {
		pages,
		label,
		note = m.pages_preview(),
		start = null,
		end,
		onpage
	}: {
		pages: readonly ShownPage[];
		label: string;
		/** Said in the toolbar beside the page count. */
		note?: string | null;
		/** How the viewer starts (`PageViewer`). */
		start?: Layout | null;
		/** At the end of the toolbar (the switch of a pane). */
		end?: Snippet;
		/** The page in the upper third of the view, and how many there are. */
		onpage?: (current: number, total: number) => void;
	} = $props();

	/** An image is as wide as its page: 100 % is A4's width; its height once it is loaded. */
	const WIDTH = 793;
	// Each page's height to its width, unturned.
	let aspects = $state<Record<number, number>>({});
	const aspectOf = (number: number) => aspects[number] ?? Math.SQRT2;
	const sideways = (page: ShownPage | undefined) => page?.turn === 90 || page?.turn === 270;
	const sizes = $derived(
		pages.map((page, index) => ({
			width: WIDTH,
			height: WIDTH * (sideways(page) ? 1 / aspectOf(index + 1) : aspectOf(index + 1))
		}))
	);
	// Spelled out, for Tailwind to find them.
	const TURNED = { 0: '', 90: 'rotate-90', 180: 'rotate-180', 270: '-rotate-90' } as const;

	let viewer = $state<PageViewer | null>(null);

	/** Scroll so that `place` stands in the upper third of the view. */
	export function reveal(place: Place) {
		viewer?.reveal(place);
	}
</script>

<PageViewer bind:this={viewer} {sizes} {label} {note} {start} {end} {onpage}>
	{#snippet page(number: number)}
		{@const shown = pages[number - 1]}
		{@const aspect = aspectOf(number)}
		<!-- Turned sideways, the image is as wide as the box is high, and the other way round. -->
		<span
			class="relative block size-full overflow-hidden"
			role="img"
			aria-label={m.page_image({ number })}
		>
			<span
				class={[
					'absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
					TURNED[shown?.turn ?? 0]
				]}
				style:width={sideways(shown) ? `${100 / aspect}%` : '100%'}
				style:height={sideways(shown) ? `${100 * aspect}%` : '100%'}
			>
				{#if shown}
					<PageImage
						src={shown.src}
						class="size-full object-contain"
						onsize={(width, height) => (aspects[number] = height / width)}
					/>
				{/if}
			</span>
		</span>
	{/snippet}
</PageViewer>
