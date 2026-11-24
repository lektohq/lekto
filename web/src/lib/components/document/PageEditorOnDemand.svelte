<script lang="ts">
	import type { ComponentProps } from 'svelte';
	import type PageEditorPart from './PageEditor.svelte';

	// The page editor, loaded when it first opens (WP-K04): few open it, and its code (the pages,
	// the cuts, the files to add) is not every document's. It stays once loaded, for its way out.
	let { open = $bindable(false), ...rest }: ComponentProps<typeof PageEditorPart> = $props();

	let wanted = $state(false);
	$effect(() => {
		if (open) wanted = true;
	});
</script>

{#if wanted}
	{#await import('./PageEditor.svelte') then { default: PageEditor }}
		<PageEditor bind:open {...rest} />
	{/await}
{/if}
