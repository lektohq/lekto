<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The owl's head of `static/favicon.svg` before the wordmark (Tobi, 06.11.2026; web/DESIGN.md,
	// "Logo and owl"): one eye is the magnifier, the other reads. In the brand colour (lighter in
	// the dark theme, the strokes then dark for contrast) and sized by the writing, wherever the
	// logo stands: the header, the navigation sheet, the sign-in and the error page. Screen readers
	// hear the name.
	let { class: className = '' }: { class?: string } = $props();
</script>

<span
	class={cn(
		'inline-flex items-center gap-[0.45em] font-mono font-medium tracking-tight',
		className
	)}
	aria-label={m.app_name()}
	role="img"
>
	<svg viewBox="0 0 32 32" class="size-[1.2em] shrink-0 text-brand" aria-hidden="true">
		<path
			d="M0 4.2Q0 1 2.8 2.3L10.6 6.3Q16 4.9 21.4 6.3L29.2 2.3Q32 1 32 4.2V24Q32 32 24 32H8Q0 32 0 24Z"
			fill="currentColor"
		/>
		<g fill="none" class="stroke-primary-foreground" stroke-width="2.6">
			<circle cx="10.5" cy="15" r="4.4" />
			<circle cx="21.5" cy="15" r="4.4" />
		</g>
		<circle cx="11.3" cy="15.8" r="1.7" class="fill-primary-foreground" />
		<path
			d="M24.6 18.1L27.2 20.7"
			class="stroke-primary-foreground"
			stroke-width="3"
			stroke-linecap="round"
		/>
		<path d="M14.8 20.4L16 22.6L17.2 20.4Z" class="fill-primary-foreground" fill-opacity="0.6" />
	</svg>
	lekto
</span>
