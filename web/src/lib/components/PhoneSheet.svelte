<script lang="ts">
	import type { Snippet } from 'svelte';
	import * as Sheet from '#lib/components/ui/sheet/index.ts';
	import { cn } from '#lib/utils.ts';

	// A sheet from the bottom (web/DESIGN.md, "Dialogs"), built on `ui/sheet`: a choice from many
	// on a phone, 85 % of the screen high, or the filters, as high as they need up to that (`fit`).
	// A grab handle, then a row fixed on top with its `title` and the way out (`close`: an X,
	// "Fertig"), then what it offers (`children`), which scrolls on its own, and `footer` fixed at
	// the bottom. Pulled down by the handle or the title it follows the finger, and closes once it
	// went far enough or was flicked; else it springs back. Nothing takes the focus when it opens:
	// the keyboard waits for a tap, and a close button shows no tooltip. A choice closes it: the
	// caller sets `open` false.
	let {
		open = $bindable(false),
		title,
		fit = false,
		onOpenChange,
		close,
		children,
		footer
	}: {
		open?: boolean;
		/** The sheet's heading: "Kontakt wählen". */
		title: string;
		/** As high as its content needs (the filters), not always 85 %. */
		fit?: boolean;
		/** Hears of the sheet closing by itself (Escape, a tap outside, a pull). */
		onOpenChange?: (open: boolean) => void;
		/** The button at the right of the title that closes the sheet. */
		close: Snippet;
		children: Snippet;
		/** What stays at the bottom: the filters' "Zurücksetzen" and "Ergebnisse anzeigen". */
		footer?: Snippet;
	} = $props();

	/** How far a pull closes the sheet (px), and how fast a flick closes it (px per ms). */
	const FAR = 96;
	const FLICK = 0.5;
	/** The slide out of a pulled sheet, as long as `ui/sheet`'s transition. */
	const SLIDE = 200;

	let sheet = $state<HTMLElement | null>(null);
	let offset = $state(0);
	let pulling = $state(false);
	// Pulled out: it leaves by its own slide. The closing animation of `ui/sheet` would start
	// from there and carry it back up while it fades, so it is switched off on the element.
	let gone = $state(false);
	const style = $derived(
		[offset > 0 && `transform: translateY(${offset}px)`, gone && 'animation: none']
			.filter(Boolean)
			.join('; ') || undefined
	);
	let pull = { start: 0, last: 0, time: 0, speed: 0 };

	$effect(() => {
		if (open) {
			offset = 0;
			gone = false;
		}
	});

	function grab(event: PointerEvent) {
		if (!event.isPrimary || (event.target as Element).closest('button')) return;
		(event.currentTarget as Element).setPointerCapture?.(event.pointerId);
		pull = { start: event.clientY, last: event.clientY, time: event.timeStamp, speed: 0 };
		pulling = true;
	}

	function drag(event: PointerEvent) {
		if (!pulling) return;
		const elapsed = Math.max(1, event.timeStamp - pull.time);
		pull = {
			...pull,
			last: event.clientY,
			time: event.timeStamp,
			speed: (event.clientY - pull.last) / elapsed
		};
		offset = Math.max(0, event.clientY - pull.start);
	}

	function release() {
		if (!pulling) return;
		pulling = false;
		if (offset < FAR && !(offset > 0 && pull.speed > FLICK)) {
			offset = 0;
			return;
		}
		gone = true;
		offset = sheet?.offsetHeight ?? offset;
		const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		window.setTimeout(
			() => {
				open = false;
				onOpenChange?.(false);
			},
			still ? 0 : SLIDE
		);
	}
</script>

<Sheet.Root bind:open {onOpenChange}>
	<Sheet.Content
		bind:ref={sheet}
		side="bottom"
		showCloseButton={false}
		onOpenAutoFocus={(event) => event.preventDefault()}
		{style}
		class={cn(
			'gap-0 overflow-hidden rounded-t-2xl p-0 text-base',
			fit ? 'max-h-[85dvh]' : 'h-[85dvh] max-h-[85dvh]',
			pulling && 'transition-none'
		)}
	>
		<!-- The pull is a shortcut for the finger; the close button is the way for everyone. -->
		<div
			role="presentation"
			class="shrink-0 touch-none"
			onpointerdown={grab}
			onpointermove={drag}
			onpointerup={release}
			onpointercancel={release}
		>
			<span class="mx-auto mt-2 block h-1.5 w-10 rounded-full bg-border" aria-hidden="true"></span>
			<div class="flex items-center justify-between gap-2 py-2 pr-2 pl-4">
				<Sheet.Title class="text-base font-semibold">{title}</Sheet.Title>
				{@render close()}
			</div>
		</div>
		{@render children()}
		{#if footer}
			<Sheet.Footer class="flex-row border-t py-3">{@render footer()}</Sheet.Footer>
		{/if}
	</Sheet.Content>
</Sheet.Root>
