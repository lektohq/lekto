<script lang="ts">
	import { api } from '#lib/api/client.ts';
	import type { components } from '#lib/api/schema.ts';
	import { openBeam } from '#lib/beam.svelte.ts';
	import BeamTitle from '#lib/components/BeamTitle.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';
	import { session } from '#lib/session.svelte.ts';

	// The documents an action on many or a rule's application left as they were, each with why
	// ("Details" of its toast): the first `SHOWN` by title (one the caller no longer reads by its
	// reason alone), the rest counted.
	let {
		operation,
		onclose
	}: {
		operation: { skipped: components['schemas']['SkippedOut'][] } | null;
		onclose: () => void;
	} = $props();

	const SHOWN = 50;
	let titles = $state<Record<string, string | null>>({});

	const rows = $derived(operation?.skipped.slice(0, SHOWN) ?? []);
	const more = $derived(Math.max(0, (operation?.skipped.length ?? 0) - SHOWN));

	// The titles of the rows in one request (the list takes up to 100 ids, every lane); a
	// document it does not bring, gone or not readable, shows by its reason alone. An admin sees
	// every user's titles, as the action reached them.
	$effect(() => {
		const ids = rows.map((row) => row.document_id);
		if (ids.length === 0) return;
		let current = true;
		api
			.GET('/api/v1/documents', {
				params: {
					query: { ids, limit: SHOWN, all_users: session.isAdmin || undefined }
				}
			})
			.then(({ data }) => {
				if (!current) return;
				const found = new Map((data?.items ?? []).map((item) => [item.id, item.title]));
				titles = Object.fromEntries(ids.map((id) => [id, found.get(id) ?? null]));
			})
			.catch(() => {
				if (current) titles = Object.fromEntries(ids.map((id) => [id, null]));
			});
		return () => {
			current = false;
		};
	});
</script>

<Dialog.Root open={operation !== null} onOpenChange={(open) => !open && onclose()}>
	<Dialog.Content size="md">
		<Dialog.Header>
			<Dialog.Title>{m.bulk_details_title()}</Dialog.Title>
			<Dialog.Description>
				{m.bulk_skipped({ count: formatNumber(operation?.skipped.length ?? 0) })}
			</Dialog.Description>
		</Dialog.Header>
		<ul class="flex max-h-[60vh] flex-col divide-y overflow-y-auto">
			{#each rows as row (row.document_id)}
				{@const title = titles[row.document_id]}
				<li class="flex flex-col gap-0.5 py-2">
					{#if title}
						<BeamTitle
							{title}
							class="max-w-full self-start"
							onview={() =>
								openBeam(
									rows.flatMap((each) => (titles[each.document_id] ? [each.document_id] : [])),
									row.document_id,
									m.bulk_details_title()
								)}
						/>
					{:else}
						<span class="font-medium text-muted-foreground">{m.bulk_unknown_document()}</span>
					{/if}
					<span class="text-sm text-muted-foreground">
						{row.reasons?.[0] ? reasonText(row.reasons[0]) : row.reason}
					</span>
				</li>
			{/each}
		</ul>
		{#if more > 0}
			<p class="text-sm text-muted-foreground">
				{m.bulk_details_more({ count: formatNumber(more) })}
			</p>
		{/if}
		<Dialog.Footer>
			<Button onclick={onclose}>{m.close()}</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
