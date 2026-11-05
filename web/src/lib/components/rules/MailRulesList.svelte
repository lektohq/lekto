<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import EditButton from '#lib/components/EditButton.svelte';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { summaryOf, type MailRule } from '#lib/mail-rules.ts';
	import type { Mailbox } from '#lib/mailboxes.ts';
	import {
		userChoice,
		type DocumentType,
		type Space,
		type UserName
	} from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';

	// The mail rules (Tobi, 04.11.2026; mock D): one section per mailbox, its rules in the order
	// they are asked (priority, then name), the first that matches decides; below them the
	// mailbox's fallback, changed at the mailbox. A row's name opens its editor (there is no
	// detail page); the switch pauses it, the pencil edits it.
	let {
		rules = $bindable(),
		mailboxes,
		users,
		spaces,
		types
	}: {
		rules: MailRule[];
		mailboxes: Mailbox[];
		users: UserName[];
		spaces: Space[];
		types: DocumentType[];
	} = $props();

	let busy = $state<string | null>(null);

	const names = {
		user: (id: string | null | undefined) => {
			const user = users.find((entry) => entry.id === id);
			return user ? userChoice(user) : m.rule_unknown();
		},
		space: (id: string | null | undefined) =>
			spaces.find((entry) => entry.id === id)?.name ?? m.rule_unknown(),
		type: (id: string | null | undefined) =>
			types.find((entry) => entry.id === id)?.name ?? m.rule_unknown()
	};

	const fallback = (mailbox: Mailbox) =>
		mailbox.fallback === 'everything'
			? m.mail_rules_fallback_everything({ name: names.user(mailbox.fallback_user_id) })
			: m.mail_rules_fallback_nothing();

	async function switchRule(rule: MailRule, enabled: boolean) {
		busy = rule.id;
		try {
			const changed = await unwrap(
				api.PATCH('/api/v1/mail-rules/{id}', {
					params: { path: { id: rule.id } },
					body: { enabled }
				})
			);
			rules = rules.map((entry) => (entry.id === changed.id ? changed : entry));
			toast.success(enabled ? m.rule_switched_on() : m.rule_switched_off());
		} catch (error) {
			reportError(error);
		} finally {
			busy = null;
		}
	}
</script>

{#if mailboxes.length === 0}
	<EmptyNote>
		{m.mail_rules_no_mailbox()}
		{#snippet action()}
			<a
				href="{BASE}/system?tab=intake"
				class="text-sm text-brand underline-offset-4 hover:underline"
				>{m.mail_rules_to_mailboxes()}</a
			>
		{/snippet}
	</EmptyNote>
{:else}
	<div class="flex flex-col gap-6">
		{#each mailboxes as mailbox (mailbox.id)}
			{@const own = rules.filter((rule) => rule.mailbox_id === mailbox.id)}
			<section class="flex flex-col gap-2" aria-labelledby="mail-rules-{mailbox.id}">
				<div class="flex flex-wrap items-baseline justify-between gap-2">
					<SectionTitle size="card" id="mail-rules-{mailbox.id}"
						>{m.mail_rules_mailbox({ name: mailbox.name })}</SectionTitle
					>
					<a
						href="{BASE}/system?tab=intake"
						class="text-sm text-brand underline-offset-4 hover:underline"
						>{m.mail_rules_to_mailbox()}</a
					>
				</div>
				<ul class="flex flex-col gap-2">
					{#each own as rule (rule.id)}
						<Card.Root as="li" size="row" class="relative flex flex-wrap items-center gap-3">
							<div class="flex min-w-0 flex-1 flex-col gap-1">
								<a
									href="{BASE}/rules/mail/{rule.id}"
									class="truncate font-medium after:absolute after:inset-0 hover:underline"
									aria-label={m.rule_open({ name: rule.name })}>{rule.name}</a
								>
								<span class="text-sm text-muted-foreground">{summaryOf(rule, names)}</span>
								{#if rule.disabled_reason}
									<span class="text-sm text-destructive"
										>{m.rule_disabled_reason({ reason: reasonText(rule.disabled_reason) })}</span
									>
								{/if}
							</div>
							<Switch
								bind:checked={() => rule.enabled, (enabled) => switchRule(rule, enabled)}
								disabled={busy === rule.id}
								class="relative z-10"
								aria-label={rule.enabled
									? m.rule_switch_off({ name: rule.name })
									: m.rule_switch_on({ name: rule.name })}
							/>
							<EditButton
								class="relative z-10"
								label={m.rule_edit_title({ name: rule.name })}
								href="{BASE}/rules/mail/{rule.id}/edit"
							/>
						</Card.Root>
					{/each}
				</ul>
				<p class="text-sm text-muted-foreground">
					{fallback(mailbox)}
					<a href="{BASE}/system?tab=intake" class="text-brand underline-offset-4 hover:underline"
						>{m.mail_rules_fallback_change()}</a
					>
				</p>
			</section>
		{/each}
	</div>
{/if}
