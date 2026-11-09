<script lang="ts">
	import { page } from '$app/state';
	import { m } from '#lib/paraglide/messages.js';
	import { BASE } from '#lib/base.ts';
	import { openLens } from '#lib/open-lens.svelte.ts';
	import { warmSearch } from '#lib/meaning-search.ts';
	import { gotoSearching, stateWords } from '#lib/words.ts';
	import SearchField from '#lib/components/SearchField.svelte';

	// The search field of the header: Enter searches the documents with the words (and, in the
	// document view, the filters already set, and its lens, which it names); `/` jumps here from
	// anywhere but a field one types into. On a desktop the document view has no field of its
	// own: this is it.
	let { class: className = '' }: { class?: string } = $props();

	let input = $state<HTMLInputElement | null>(null);
	const DOCUMENTS = `${BASE}/documents`;
	const inDocuments = $derived(page.url.pathname === DOCUMENTS);
	// In the document view the field shows what is searched for, until the user types: the
	// words of the history entry, or those of the lens a plain link opened (`lib/words.ts`).
	let text = $derived(inDocuments ? (stateWords(page.state) ?? openLens.query ?? '') : '');

	function submit(event: SubmitEvent) {
		event.preventDefault();
		// Built and read at once, nothing reacts to it.
		// eslint-disable-next-line svelte/prefer-svelte-reactivity
		const params = new URLSearchParams(inDocuments ? page.url.search : '');
		params.delete('sort'); // a search sorts as the last search did
		const query = params.toString();
		// The words go into the history entry, never into the address.
		void gotoSearching(query ? `${DOCUMENTS}?${query}` : DOCUMENTS, text.trim());
	}

	function keydown(event: KeyboardEvent) {
		if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
		const target = event.target as HTMLElement | null;
		const typing =
			target !== null &&
			(target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName));
		if (typing) return;
		event.preventDefault();
		input?.focus();
	}
</script>

<svelte:window onkeydown={keydown} />

<form role="search" onsubmit={submit} class={className}>
	<SearchField
		bind:ref={input}
		class="flex-1"
		bind:value={text}
		label={m.header_search_label()}
		placeholder={inDocuments && openLens.name
			? m.header_search_in({ name: openLens.name })
			: m.header_search_placeholder()}
		oninput={() => warmSearch()}
	>
		{#snippet end()}
			<kbd
				class="rounded-md border bg-card px-1.5 font-mono text-micro leading-5 text-muted-foreground"
				aria-hidden="true">/</kbd
			>
		{/snippet}
	</SearchField>
</form>
