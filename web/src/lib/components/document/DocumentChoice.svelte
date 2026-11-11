<script lang="ts">
	import { untrack } from 'svelte';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import FormDialog from '#lib/components/FormDialog.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import { formatDate } from '#lib/i18n.ts';
	import { mergeBlock, type Candidate } from '#lib/merge.ts';
	import { m } from '#lib/paraglide/messages.js';

	// "Dokument aus Lekto wählen" (web/DESIGN.md, "Page stack"): a document whose pages join the
	// stack of "PDF bearbeiten", which merges the documents when applied. At first the newest
	// the user may read; typing searches the words of all of them. A document that cannot join
	// stands there disabled with why (on the stack already, a mail, being processed, not the
	// user's to edit, without page images).
	let {
		open = $bindable(false),
		there,
		onpick
	}: {
		open?: boolean;
		/** The documents on the stack already. */
		there: readonly string[];
		onpick: (document: Candidate) => void;
	} = $props();

	let query = $state('');
	let recent = $state<Candidate[]>([]);
	let found = $state<Candidate[] | null>(null);
	let picked = $state<string | null>(null);

	let shown = false;
	$effect(() => {
		if (open && !shown) untrack(start);
		shown = open;
	});

	function start() {
		query = '';
		found = null;
		picked = null;
		void unwrap(api.GET('/api/v1/documents', { params: { query: { limit: 50 } } })).then(
			(page) => (recent = page.items),
			() => (recent = [])
		);
	}

	$effect(() => {
		const text = query.trim();
		found = null;
		if (!text) return;
		let current = true;
		const timer = setTimeout(() => {
			void unwrap(
				api.POST('/api/v1/documents/search', {
					params: { query: { limit: 20, semantic_ratio: 0 } },
					body: { q: text }
				})
			).then(
				(page) => {
					if (current) found = page.items.map((item) => item.document);
				},
				() => {
					const wanted = text.toLocaleLowerCase();
					if (current) {
						found = untrack(() => recent).filter((item) =>
							item.title.toLocaleLowerCase().includes(wanted)
						);
					}
				}
			);
		}, 250);
		return () => {
			current = false;
			clearTimeout(timer);
		};
	});

	const rows = $derived(
		(found ?? recent).map((document) => ({ document, reason: mergeBlock(document, there) }))
	);

	const pages = (count: number | null) =>
		count === 1 ? m.page_edit_pages_one() : m.page_edit_pages({ count: String(count ?? 0) });

	async function add() {
		const row = rows.find((item) => item.document.id === picked && item.reason === null);
		if (!row) return;
		onpick(row.document);
		open = false;
	}
</script>

<FormDialog
	bind:open
	title={m.pick_document_title()}
	description={m.pick_document_description()}
	submitLabel={m.pick_document_add()}
	disabled={picked === null}
	size="md"
	action={add}
>
	<SearchField bind:value={query} label={m.pick_document_search()} />
	{#if rows.length === 0}
		<p class="py-4 text-center text-sm text-muted-foreground">{m.pick_document_empty()}</p>
	{:else}
		<div role="radiogroup" aria-label={m.pick_document_title()} class="flex flex-col">
			{#each rows as { document, reason } (document.id)}
				<Choice
					type="radio"
					name="pick-document"
					value={document.id}
					bind:group={picked}
					disabled={reason !== null}
					class="w-full max-w-full border-b py-2.5 last:border-b-0"
				>
					<span class="flex min-w-0 flex-col">
						<span class="truncate font-medium">{document.title}</span>
						<span class="truncate text-meta text-muted-foreground">
							{formatDate(document.created_at)} · {pages(document.page_count)}{reason
								? ` · ${reason}`
								: ''}
						</span>
					</span>
				</Choice>
			{/each}
		</div>
	{/if}
</FormDialog>
