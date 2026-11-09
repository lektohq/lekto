<script lang="ts">
	import { switchMailRule } from '#lib/rules/switch.ts';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import MailRuleView from '#lib/components/rules/MailRuleView.svelte';
	import RuleHeader from '#lib/components/rules/RuleHeader.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { describeError } from '#lib/errors.ts';
	import { loadMailRuleLookup, namesOf, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import type { MailRule } from '#lib/mail-rules.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';

	// A mail rule's page, as a document rule's (Tobi, 05.11.2026): its name, the switch,
	// "Bearbeiten", "Probelauf" and delete in the head; its mailbox and priority below; the rule
	// to read.
	const id = $derived(page.params.id ?? '');
	let rule = $state<MailRule | null>(null);
	let lookup = $state<MailRuleLookup | null>(null);
	let problem = $state<string | null>(null);
	let busy = $state(false);
	let removing = $state(false);

	const mailbox = $derived(
		lookup?.mailboxes.find((entry) => entry.id === rule?.mailbox_id)?.name ?? m.rule_unknown()
	);

	async function load(wanted: string) {
		problem = null;
		try {
			const [found, loaded] = await Promise.all([
				unwrap(api.GET('/api/v1/mail-rules/{id}', { params: { path: { id: wanted } } })),
				lookup ?? loadMailRuleLookup()
			]);
			[rule, lookup] = [found, loaded];
		} catch (error) {
			problem = describeError(error);
		}
	}

	$effect(() => {
		const wanted = id;
		untrack(() => void load(wanted));
	});

	async function switchOne(enabled: boolean) {
		if (!rule) return;
		busy = true;
		rule = (await switchMailRule(rule.id, enabled)) ?? rule;
		busy = false;
	}

	async function remove() {
		await unwrap(api.DELETE('/api/v1/mail-rules/{id}', { params: { path: { id } } }));
		toast.success(m.rule_deleted());
		await goto(`${BASE}/rules?kind=mail`);
	}
</script>

<svelte:head><title>{rule?.name ?? m.nav_rules()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<RuleHeader
		title={rule?.name ?? m.mail_rule_generic()}
		back={{ href: `${BASE}/rules?kind=mail`, label: m.nav_rules() }}
		{rule}
		{busy}
		editHref="{BASE}/rules/mail/{id}/edit"
		applyHref="{BASE}/rules/mail/{id}/apply"
		disabledReason={rule?.disabled_reason ? reasonText(rule.disabled_reason) : null}
		onswitch={switchOne}
		ondelete={() => (removing = true)}
	>
		{#snippet badges()}
			<Badge variant="note">{m.mail_rules_mailbox({ name: mailbox })}</Badge>
		{/snippet}
	</RuleHeader>

	{#if problem}
		<LoadProblem {problem} onretry={() => void load(id)} />
	{:else if !rule || !lookup}
		<Loading />
	{:else}
		<Card.Root as="section">
			<MailRuleView {rule} {mailbox} names={namesOf(lookup)} />
		</Card.Root>
	{/if}
</div>

<ConfirmDialog
	bind:open={removing}
	title={m.rule_delete({ name: rule?.name ?? '' })}
	description={m.mail_rule_delete_confirm()}
	confirmLabel={m.delete_title()}
	onconfirm={remove}
/>
