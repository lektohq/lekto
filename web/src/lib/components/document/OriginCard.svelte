<script lang="ts">
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { formatDate } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';

	type MailOrigin = components['schemas']['MailOriginOut'];
	type Address = components['schemas']['AddressOut'];

	// Where the document came from (Tobi, 04.11.2026; mock C): for one a mail brought, the
	// mailbox, the rule that took it (or the mailbox's fallback), sender, recipients, subject,
	// when it arrived and who forwarded it. Other documents show no card.
	let { documentId }: { documentId: string } = $props();

	let mail = $state<MailOrigin | null>(null);

	$effect(() => {
		const id = documentId;
		mail = null;
		void load(id);
	});

	async function load(id: string) {
		try {
			const origin = await unwrap(
				api.GET('/api/v1/documents/{id}/origin', { params: { path: { id } } })
			);
			if (id === documentId) mail = origin.mail;
		} catch (error) {
			reportError(error);
		}
	}

	const people = (list: readonly Address[]) =>
		list.map((item) => (item.name ? `${item.name} <${item.address}>` : item.address)).join(', ');
	const moment = (value: string) => formatDate(value, { dateStyle: 'medium', timeStyle: 'short' });

	const rows = $derived(
		mail
			? ([
					[m.origin_channel(), m.origin_channel_mail()],
					[m.origin_mailbox(), mail.mailbox],
					[m.origin_rule(), mail.rule ?? m.origin_fallback()],
					[m.origin_from(), people(mail.sender)],
					[m.origin_to(), people(mail.to)],
					[m.origin_subject(), mail.subject],
					[m.origin_received(), moment(mail.arrived_at)],
					[m.origin_forwarded(), people(mail.forwarded_by)],
					[m.origin_file(), mail.role === 'attachment' ? (mail.filename ?? '') : '']
				].filter(([, value]) => value) as [string, string][])
			: []
	);
</script>

{#if mail}
	<Card.Root as="section" size="sm" aria-labelledby="origin-title">
		<div class="px-1 pb-1">
			<SectionTitle size="card" id="origin-title">{m.origin_title()}</SectionTitle>
		</div>
		<dl class="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-x-3 gap-y-1.5 px-1 pb-1 text-sm">
			{#each rows as [label, value] (label)}
				<dt class="text-muted-foreground">{label}</dt>
				<dd class="break-words">{value}</dd>
			{/each}
		</dl>
	</Card.Root>
{/if}
