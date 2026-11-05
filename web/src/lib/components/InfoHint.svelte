<script lang="ts">
	import InfoTip from '#lib/components/InfoTip.svelte';
	import { m } from '#lib/paraglide/messages.js';

	// The help of a field behind a small info button beside its label, not under the field
	// (Tobi, 20.10.2026), in the box of every info icon (`InfoTip`). With `id` the text is also
	// there hidden, for the field's `aria-describedby`. The button reaches over the label's line
	// without making it higher, so a label with help is as high as one without and fields side by
	// side start on one line.
	let { text, about, id }: { text: string; about: string; id?: string } = $props();
</script>

<span class="-my-1 flex">
	<InfoTip label={m.hint_about({ name: about })} size="sm" class="w-80">
		<p>{text}</p>
	</InfoTip>
</span>
{#if id}<span {id} hidden>{text}</span>{/if}
