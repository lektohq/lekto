<script lang="ts" module>
	import type { VariantProps } from 'tailwind-variants';
	import { tv } from '#lib/tailwind.ts';

	// Every card (web/DESIGN.md, "Cards"): the radius of cards, a hairline border, no shadow; the
	// layout inside is the caller's (`class`). The size sets the padding: `row` for items of a list, `sm` for dense panels, `md` by default,
	// `lg` for the sections of the system page, `flush` for a card whose rows or parts pad
	// themselves.
	export const cardVariants = tv({
		base: 'group/card min-w-0 rounded-2xl border text-card-foreground',
		variants: {
			// `open`: what waits for an answer of the person (the filing question, a field to
			// check), on the yellow of its lane (web/DESIGN.md, "Cards").
			// `nested`: a card inside a card of its kind (a group of conditions in a group);
			// `inset`: a row inside a card, on the page's ground (a condition, an action).
			tone: {
				plain: 'bg-card',
				open: 'border-lane-yellow-foreground/25 bg-lane-yellow/25',
				nested: 'bg-secondary/40',
				inset: 'bg-background'
			},
			size: {
				flush: '',
				row: 'p-4',
				sm: 'p-3.5',
				md: 'p-5',
				lg: 'px-5 py-4 sm:px-6'
			}
		},
		defaultVariants: { size: 'md', tone: 'plain' }
	});

	export type CardSize = VariantProps<typeof cardVariants>['size'];
	export type CardTone = VariantProps<typeof cardVariants>['tone'];
</script>

<script lang="ts">
	import { cn, type WithElementRef } from '#lib/utils.ts';
	import type { HTMLAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		class: className,
		children,
		size = 'md',
		tone = 'plain',
		as = 'div',
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLElement>> & {
		size?: CardSize;
		tone?: CardTone;
		as?: 'div' | 'section' | 'article' | 'li' | 'ul' | 'ol' | 'aside' | 'form';
	} = $props();
</script>

<svelte:element
	this={as}
	bind:this={ref}
	data-slot="card"
	data-size={size}
	class={cn(cardVariants({ size, tone }), className)}
	{...restProps}
>
	{@render children?.()}
</svelte:element>
