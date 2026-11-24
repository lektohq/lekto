<script lang="ts">
	import type { Snippet } from 'svelte';

	// The head of a pane of the document tab: what the pane says and does at the start, its
	// switch at the end; as high as the toolbar of the pages, so the heads of both panes line up.
	let { children, end }: { children?: Snippet; end?: Snippet } = $props();
</script>

<div class="@container flex flex-wrap items-center gap-x-2 gap-y-1 border-b bg-card px-3 py-2">
	<!-- As high as an icon button: the toolbar of the pages is (`ICON_BUTTON_ROOM`). -->
	<div class="flex min-h-10 min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
		{@render children?.()}
	</div>
	{@render end?.()}
</div>
