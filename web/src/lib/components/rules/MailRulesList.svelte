<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import RuleListRow from '#lib/components/rules/RuleListRow.svelte';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { namesOf, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import { summaryOf, type MailRule } from '#lib/mail-rules.ts';
	import type { Mailbox } from '#lib/mailboxes.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';
	import { cn } from '#lib/utils.ts';

	// The mail rules (Tobi, 04.11.2026; mock D): one section per mailbox, its rules in the order
	// they are asked (priority, then name), the first that matches decides; below them the
	// mailbox's fallback, changed at the mailbox. A row's name opens the rule's page; the
	// switch pauses it, the pencil edits it. "Postfach ansehen" opens the mailbox's dialog, "Neue
	// Regel" makes a rule for that mailbox (Tobi, 05.11.2026). `lookup`: what the rules name
	// (every space).
	let { rules = $bindable(), lookup }: { rules: MailRule[]; lookup: MailRuleLookup } = $props();

	let busy = $state<string | null>(null);

	const mailboxes = $derived(lookup.mailboxes);
	const names = $derived(namesOf(lookup));
	const textLink = cn(buttonVariants({ variant: 'link', size: 'inline' }));

	const fallback = (mailbox: Mailbox) =>
		mailbox.fallback === 'everything'
			? m.mail_rules_fallback_everything({ name: names.user(mailbox.fallback_user_id) })
			: m.mail_rules_fallback_nothing();

	const mailboxHref = (mailbox: Mailbox) => `${BASE}/system?tab=intake&mailbox=${mailbox.id}`;

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
			<a href="{BASE}/system?tab=intake" class={textLink}>{m.mail_rules_to_mailboxes()}</a>
		{/snippet}
	</EmptyNote>
{:else}
	<div class="flex flex-col gap-6">
		{#each mailboxes as mailbox (mailbox.id)}
			{@const own = rules.filter((rule) => rule.mailbox_id === mailbox.id)}
			<section class="flex flex-col gap-2" aria-labelledby="mail-rules-{mailbox.id}">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<SectionTitle size="card" id="mail-rules-{mailbox.id}"
						>{m.mail_rules_mailbox({ name: mailbox.name })}</SectionTitle
					>
					<span class="flex flex-wrap items-center gap-3">
						<a href={mailboxHref(mailbox)} class={textLink}>{m.mail_rules_to_mailbox()}</a>
						<a
							href="{BASE}/rules/mail/new?mailbox={mailbox.id}"
							class={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
							aria-label={m.mail_rules_new_for({ name: mailbox.name })}
						>
							<Plus aria-hidden="true" />
							{m.rules_new()}
						</a>
					</span>
				</div>
				<ul class="flex flex-col gap-2">
					{#each own as rule (rule.id)}
						<RuleListRow
							href="{BASE}/rules/mail/{rule.id}"
							editHref="{BASE}/rules/mail/{rule.id}/edit"
							name={rule.name}
							enabled={rule.enabled}
							busy={busy === rule.id}
							disabledReason={rule.disabled_reason ? reasonText(rule.disabled_reason) : null}
							onswitch={(enabled) => switchRule(rule, enabled)}
						>
							{#snippet summary()}{summaryOf(rule, names)}{/snippet}
						</RuleListRow>
					{/each}
				</ul>
				<p class="text-sm text-muted-foreground">
					{fallback(mailbox)}
					<a href={mailboxHref(mailbox)} class={textLink}>{m.mail_rules_fallback_change()}</a>
				</p>
			</section>
		{/each}
	</div>
{/if}
