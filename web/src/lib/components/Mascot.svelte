<script lang="ts">
	import { cn } from '#lib/utils.ts';

	// The owl of the logo as a figure (Tobi, 06.11.2026; web/DESIGN.md, "Logo and owl"): its face
	// is the logo's, its belly the three lines of a page, and it sits on a line. It stands only
	// where a moment is rare and means something: the sign-in, the page that does not exist, the
	// inbox with nothing waiting and the documents before the first one. In the brand colour like
	// the logo; the words beside it say what there is to say, so screen readers skip it. `class`
	// sets its width, the height follows.
	let { class: className = '' }: { class?: string } = $props();
</script>

<svg
	viewBox="0 0 40 50"
	class={cn('aspect-[4/5] h-auto shrink-0 text-brand', className)}
	aria-hidden="true"
	data-mascot
>
	<path
		d="M4 7Q4 3.6 7 5L14.2 9.1Q20 7.7 25.8 9.1L33 5Q36 3.6 36 7V31Q36 45 20 45Q4 45 4 31Z"
		fill="currentColor"
	/>
	<g fill="none" class="stroke-primary-foreground" stroke-width="2.7">
		<circle cx="14" cy="18" r="4.7" />
		<circle cx="26" cy="18" r="4.7" />
	</g>
	<circle cx="14.8" cy="18.8" r="1.9" class="fill-primary-foreground" />
	<path
		d="M29.4 21.4L32.2 24.2"
		class="stroke-primary-foreground"
		stroke-width="3"
		stroke-linecap="round"
	/>
	<path d="M18.6 23.6L20 26.2L21.4 23.6Z" class="fill-primary-foreground" fill-opacity="0.6" />
	<path
		d="M13 31.5H27M13 35.5H23M13 39.5H25"
		fill="none"
		class="stroke-primary-foreground"
		stroke-opacity="0.6"
		stroke-width="2.2"
		stroke-linecap="round"
	/>
	<path
		d="M15 45V48M25 45V48M2 48.5H38"
		fill="none"
		stroke="currentColor"
		stroke-width="2.2"
		stroke-linecap="round"
	/>
</svg>
