<script lang="ts">
	import type { HTMLLabelAttributes } from 'svelte/elements';
	import PageImage from '#lib/components/pages/PageImage.svelte';
	import { ChoiceBox } from '#lib/components/ui/choice/index.ts';
	import { cn } from '#lib/utils.ts';

	// A page of a stack to edit (web/DESIGN.md, "Page tile"): the paper of the page in a square,
	// turned as it will be, its place below ("Seite 3"), and its box at the top left. The tile
	// is the label of its box: a click or a tap anywhere chooses it, and the box is the tab stop
	// of the grid it stands in (`tabindex`, roving). Chosen, it has the chosen look of "Choosing
	// many". `ghost`: it is being moved, shown at half strength meanwhile. The grid owns the
	// choice: a click, a tap or Space calls `onchoose` (with Shift held: up to here).
	let {
		image: src,
		rotate = 0,
		label,
		chosen = false,
		ghost = false,
		tabindex = -1,
		onchoose,
		onkeydown,
		onfocus,
		...rest
	}: Omit<HTMLLabelAttributes, 'onkeydown' | 'onfocus'> & {
		image: string;
		rotate?: 0 | 90 | 180 | 270;
		/** The place on the stack, "Seite 3"; also the box's name. */
		label: string;
		chosen?: boolean;
		ghost?: boolean;
		tabindex?: number;
		/** Chosen or let go; `range`: with Shift, up to here. */
		onchoose: (range: boolean) => void;
		onkeydown?: (event: KeyboardEvent) => void;
		onfocus?: () => void;
	} = $props();

	// A click on the tile reaches the box as a click of its own, without the keys held.
	let shift = false;

	// Spelled out, for Tailwind to find them.
	const TURNED = { 0: '', 90: 'rotate-90', 180: 'rotate-180', 270: '-rotate-90' } as const;
</script>

<label
	{...rest}
	data-page-tile
	onclickcapture={(event) => {
		shift = event.shiftKey;
	}}
	class={cn(
		'flex w-32 cursor-pointer touch-manipulation flex-col gap-1.5 rounded-xl border bg-card p-2 select-none',
		chosen && 'border-primary bg-panel',
		ghost && 'opacity-50',
		rest.class
	)}
>
	<span class="relative flex size-28 items-center justify-center">
		<PageImage
			{src}
			class={cn(
				'pointer-events-none max-h-full max-w-full bg-card shadow-sm transition-transform motion-reduce:transition-none',
				TURNED[rotate]
			)}
		/>
		<ChoiceBox
			checked={chosen}
			aria-label={label}
			{tabindex}
			class="absolute top-0 left-0"
			onclick={(event) => {
				// The grid decides what is chosen (a range with Shift), not the box itself. The
				// browser puts a cancelled box back after the event, so it is set again then.
				event.preventDefault();
				const box = event.currentTarget;
				onchoose(event.shiftKey || shift);
				shift = false;
				setTimeout(() => (box.checked = chosen));
			}}
			{onkeydown}
			{onfocus}
		/>
	</span>
	<span class="text-center text-meta text-muted-foreground">{label}</span>
</label>
