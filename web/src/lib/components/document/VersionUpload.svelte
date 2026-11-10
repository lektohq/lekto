<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { apiError } from '#lib/api/problem.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import { m } from '#lib/paraglide/messages.js';

	// "Neue Fassung hochladen" (web/DESIGN.md, Glossary "Fassung"), from the card of the
	// versions or the document's menu: a file from the device (`start`), asked about, then put
	// in the place of the current version (`POST /documents/{id}/versions`): processing runs
	// again, keeps what a person confirmed, and the document waits in the inbox.
	let {
		documentId,
		title,
		current,
		onchanged
	}: {
		documentId: string;
		/** The document's title, named in the question. */
		title: string;
		/** The number of the current version, which stays (where known). */
		current?: number;
		onchanged?: () => void;
	} = $props();

	let picker = $state<HTMLInputElement | null>(null);
	let chosen = $state<File | null>(null);
	let asking = $state(false);

	/** Choose the file. */
	export function start() {
		picker?.click();
	}

	async function replace() {
		const file = chosen;
		if (!file) return;
		const form = new FormData();
		form.append('file', file, file.name);
		const { data, error, response } = await api.POST('/api/v1/documents/{id}/versions', {
			params: { path: { id: documentId } },
			// The generated type wants a string for the file; the form carries the binary.
			body: { file: '' },
			bodySerializer: () => form
		});
		if (!data) throw await apiError(response, error);
		toast.success(m.version_replaced_done());
		onchanged?.();
	}
</script>

<input
	bind:this={picker}
	type="file"
	accept="application/pdf,image/jpeg,image/png,image/tiff"
	class="hidden"
	aria-hidden="true"
	tabindex="-1"
	onchange={(event) => {
		chosen = event.currentTarget.files?.[0] ?? null;
		asking = chosen !== null;
		event.currentTarget.value = '';
	}}
/>

<!-- The current file stays as a version: nothing is lost, so no destructive look. -->
<ConfirmDialog
	bind:open={asking}
	destructive={false}
	title={m.version_replace_title({ title, file: chosen?.name ?? '' })}
	description={current === undefined
		? m.version_replace_text_kept()
		: m.version_replace_text({ number: String(current) })}
	confirmLabel={m.version_replace()}
	onconfirm={replace}
/>
