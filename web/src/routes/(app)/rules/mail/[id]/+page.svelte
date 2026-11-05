<script lang="ts">
	import Pencil from '@lucide/svelte/icons/pencil';
	import Play from '@lucide/svelte/icons/play';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import MailRuleView from '#lib/components/rules/MailRuleView.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { loadMailRuleLookup, namesOf, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import type { MailRule } from '#lib/mail-rules.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';
	import { cn } from '#lib/utils.ts';

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

	async function switchRule(enabled: boolean) {
		if (!rule) return;
		busy = true;
		try {
			rule = await unwrap(
				api.PATCH('/api/v1/mail-rules/{id}', {
					params: { path: { id: rule.id } },
					body: { enabled }
				})
			);
			toast.success(enabled ? m.rule_switched_on() : m.rule_switched_off());
		} catch (error) {
			reportError(error);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		await unwrap(api.DELETE('/api/v1/mail-rules/{id}', { params: { path: { id } } }));
		toast.success(m.rule_deleted());
		await goto(`${BASE}/rules?kind=mail`);
	}
</script>

<svelte:head><title>{rule?.name ?? m.nav_rules()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader
		title={rule?.name ?? m.mail_rule_generic()}
		back={{ href: `${BASE}/rules?kind=mail`, label: m.nav_rules() }}
	>
		{#snippet actions()}
			{#if rule}
				<Switch
					bind:checked={() => rule?.enabled ?? false, switchRule}
					disabled={busy}
					aria-label={rule.enabled
						? m.rule_switch_off({ name: rule.name })
						: m.rule_switch_on({ name: rule.name })}
				/>
				<a
					href="{BASE}/rules/mail/{rule.id}/edit"
					class={cn(buttonVariants({ variant: 'outline' }))}
				>
					<Pencil aria-hidden="true" />
					{m.rule_edit()}
				</a>
				<a
					href="{BASE}/rules/mail/{rule.id}/apply"
					class={cn(buttonVariants({ variant: 'outline' }))}
				>
					<Play aria-hidden="true" />
					{m.rule_dry_run()}
				</a>
				<IconButton label={m.rule_delete({ name: rule.name })} onclick={() => (removing = true)}>
					<Trash2 aria-hidden="true" />
				</IconButton>
			{/if}
		{/snippet}
		{#snippet below()}
			{#if rule}
				<span class="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
					<Badge variant="note">{m.mail_rules_mailbox({ name: mailbox })}</Badge>
					{m.rule_priority_short({ priority: rule.priority })}
				</span>
				{#if rule.disabled_reason}
					<span class="text-sm text-destructive">
						{m.rule_disabled_reason({ reason: reasonText(rule.disabled_reason) })}
					</span>
				{/if}
			{/if}
		{/snippet}
	</PageHeader>

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
