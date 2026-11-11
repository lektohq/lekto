<script lang="ts">
	import { cn } from '#lib/utils.ts';

	// The image of a page: a page image of the API as an `<img>`; the page of a file about to be
	// added (a `data:` URL, `POST /documents/{id}/edit/pages`) drawn on a canvas, which the
	// site's Content Security Policy (`img-src 'self'`) leaves alone. Either scales like an image
	// and says its size once it has one (`onsize`).
	let {
		src,
		class: className,
		onsize
	}: {
		src: string;
		class?: string;
		onsize?: (width: number, height: number) => void;
	} = $props();

	let canvas = $state<HTMLCanvasElement | null>(null);
	const drawn = $derived(src.startsWith('data:'));

	$effect(() => {
		const target = canvas;
		if (!drawn || !target || typeof createImageBitmap !== 'function') return;
		let current = true;
		void (async () => {
			const bitmap = await createImageBitmap(await (await fetchless(src)).blob());
			if (!current) return bitmap.close();
			target.width = bitmap.width;
			target.height = bitmap.height;
			target.getContext('2d')?.drawImage(bitmap, 0, 0);
			onsize?.(bitmap.width, bitmap.height);
			bitmap.close();
		})();
		return () => {
			current = false;
		};
	});

	/** The bytes of a `data:` URL, without a request (`connect-src` stays as it is). */
	async function fetchless(url: string): Promise<Response> {
		const [head, data] = url.split(',', 2);
		const type = head.slice('data:'.length).split(';')[0];
		const bytes = Uint8Array.from(atob(data), (char) => char.charCodeAt(0));
		return new Response(new Blob([bytes], { type }));
	}
</script>

{#if drawn}
	<canvas bind:this={canvas} width="3" height="4" class={className} aria-hidden="true"></canvas>
{:else}
	<img
		{src}
		alt=""
		loading="lazy"
		decoding="async"
		draggable="false"
		class={cn(className)}
		onload={(event) => {
			const image = event.currentTarget as HTMLImageElement;
			if (image.naturalWidth > 0) onsize?.(image.naturalWidth, image.naturalHeight);
		}}
	/>
{/if}
