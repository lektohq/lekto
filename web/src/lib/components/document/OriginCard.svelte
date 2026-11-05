<script lang="ts">
	import { flagLabel, importanceLabel } from '#lib/mail-traits.ts';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import DetailList from '#lib/components/DetailList.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Skeleton } from '#lib/components/ui/skeleton/index.ts';
	import { describeError } from '#lib/errors.ts';
	import { formatMoment } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';

	type MailOrigin = components['schemas']['MailOriginOut'];
	type Address = components['schemas']['AddressOut'];

	// Where the document came from (Tobi, 04.11.2026; mock C): for one a mail brought, the
	// mailbox, the rule that took it (or the mailbox's fallback), sender, recipients, subject,
	// when it arrived and who forwarded it. The card loads as the other cards do (a skeleton,
	// then its rows; a load error on the card, web/DESIGN.md "States"); a document whose mail
	// Lekto did not keep shows none.
	let { documentId }: { documentId: string } = $props();

	let mail = $state<MailOrigin | null>(null);
	let loading = $state(true);
	let problem = $state<string | null>(null);

	$effect(() => {
		const id = documentId;
		mail = null;
		void load(id);
	});

	async function load(id: string) {
		loading = true;
		problem = null;
		try {
			const origin = await unwrap(
				api.GET('/api/v1/documents/{id}/origin', { params: { path: { id } } })
			);
			if (id === documentId) mail = origin.mail;
		} catch (error) {
			if (id === documentId) problem = describeError(error);
		} finally {
			if (id === documentId) loading = false;
		}
	}

	// What the mail was marked with on the server shows too (Tobi, 05.11.2026).
	const people = (list: readonly Address[]) =>
		list.map((item) => (item.name ? `${item.name} <${item.address}>` : item.address)).join(', ');

	const rows = $derived(
		mail
			? ([
					[m.origin_channel(), m.origin_channel_mail()],
					[m.origin_mailbox(), mail.mailbox],
					[m.origin_rule(), mail.rule ?? m.origin_fallback()],
					[m.origin_from(), people(mail.sender)],
					[m.origin_to(), people(mail.to)],
					[m.origin_cc(), people(mail.cc)],
					[m.origin_subject(), mail.subject],
					// Normal importance says nothing; high and low do.
					[
						m.origin_importance(),
						mail.importance && mail.importance !== 'normal' ? importanceLabel(mail.importance) : ''
					],
					[m.origin_keywords(), (mail.keywords ?? []).join(', ')],
					[m.origin_flag(), mail.flag ? flagLabel(mail.flag) : ''],
					[m.origin_received(), formatMoment(mail.arrived_at)],
					[m.origin_forwarded(), people(mail.forwarded_by)],
					[m.origin_file(), mail.role === 'attachment' ? (mail.filename ?? '') : '']
				].filter(([, value]) => value) as [string, string][])
			: []
	);
</script>

{#if loading || problem || mail}
	<Card.Root as="section" size="sm" aria-labelledby="origin-title">
		<div class="px-1 pb-1">
			<SectionTitle size="card" id="origin-title">{m.origin_title()}</SectionTitle>
		</div>
		{#if loading}
			<div class="flex flex-col gap-2 px-1 pb-1" aria-hidden="true">
				<Skeleton class="h-4 w-2/3" />
				<Skeleton class="h-4 w-1/2" />
				<Skeleton class="h-4 w-3/4" />
			</div>
		{:else if problem}
			<LoadProblem {problem} onretry={() => void load(documentId)} />
		{:else}
			<DetailList {rows} class="px-1 pb-1" />
		{/if}
	</Card.Root>
{/if}
