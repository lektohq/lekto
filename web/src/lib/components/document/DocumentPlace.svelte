<script lang="ts">
	import Stepper from '#lib/components/Stepper.svelte';
	import { inboxDocument, listDocument, type Neighbours } from '#lib/document-view.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	// Where the open document stands among those of the place it was opened from, the inbox or
	// the document list, with the ones before and after it (web/DESIGN.md, "Navigation between
	// list and detail"): at the end of the head's first row, the arrows at the edge; on a phone
	// only "2 von 135", so that the row never breaks. Also where the document cannot be shown
	// (gone), so that one steps on from it.
	let { inbox, list }: { inbox: Neighbours | null; list: Neighbours | null } = $props();
</script>

{#if inbox && inbox.position !== null}
	<Stepper
		class="ml-auto"
		side="end"
		label={m.doc_inbox_nav()}
		text={phone.current
			? m.doc_position_short({ position: inbox.position, total: inbox.total })
			: m.doc_inbox_position({ position: inbox.position, total: inbox.total })}
		previous={inbox.previous ? inboxDocument(inbox.previous) : null}
		next={inbox.next ? inboxDocument(inbox.next) : null}
		previousLabel={m.doc_previous()}
		nextLabel={m.doc_next()}
	/>
{:else if list && list.position !== null}
	<Stepper
		class="ml-auto"
		side="end"
		label={m.doc_list_nav()}
		text={phone.current
			? m.doc_position_short({ position: list.position, total: list.total })
			: m.doc_list_position({ position: list.position, total: list.total })}
		previous={list.previous ? listDocument(list.previous) : null}
		next={list.next ? listDocument(list.next) : null}
		previousLabel={m.doc_previous()}
		nextLabel={m.doc_next()}
	/>
{/if}
