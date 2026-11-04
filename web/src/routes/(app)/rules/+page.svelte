<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import MailRulesList from '#lib/components/rules/MailRulesList.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import type { MailRule } from '#lib/mail-rules.ts';
	import type { Mailbox } from '#lib/mailboxes.ts';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import { BASE } from '#lib/base.ts';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import EditButton from '#lib/components/EditButton.svelte';
	import TitlePatternBadge from '#lib/components/rules/TitlePatternBadge.svelte';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import type { DocumentType, Space, UserName } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonsText } from '#lib/reasons.ts';
	import { scope } from '#lib/scope.svelte.ts';
	import { canChangeRule } from '#lib/permissions.ts';
	import { TRIGGER_LABELS } from '#lib/rules/describe.ts';
	import { placeLabel, placeOf } from '#lib/rules/places.ts';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import Loading from '#lib/components/Loading.svelte';

	type Rule = components['schemas']['RuleOut'];

	// The rules of the documents, and for admins the mail rules beside them (Tobi, 04.11.2026;
	// mock D): a `Segmented` "Dokumente | Mails" with their counts; the choice stands in the URL.
	const kind = $derived(
		session.isAdmin && page.url.searchParams.get('kind') === 'mail' ? 'mail' : 'documents'
	);
	let mailRules = $state<MailRule[] | null>(null);
	let mailboxes = $state<Mailbox[]>([]);
	let types = $state<DocumentType[]>([]);

	async function loadMail() {
		if (!session.isAdmin) return;
		try {
			[mailRules, mailboxes, types] = await Promise.all([
				unwrap(api.GET('/api/v1/mail-rules')),
				unwrap(api.GET('/api/v1/mailboxes')),
				unwrap(api.GET('/api/v1/document-types'))
			]);
		} catch (error) {
			problem = describeError(error);
		}
	}

	$effect(() => {
		void session.isAdmin;
		untrack(() => void loadMail());
	});

	let rules = $state<Rule[] | null>(null);
	let users = $state<UserName[]>([]);
	let spaces = $state<Space[]>([]);
	let problem = $state<string | null>(null);
	let busy = $state<string | null>(null);

	const placeName = (rule: Rule) =>
		placeLabel(placeOf(rule), spaces, users, session.user?.id, m.rule_global);

	let loads = 0;

	async function load() {
		const current = ++loads;
		try {
			const [found, names, known] = await Promise.all([
				unwrap(
					api.GET('/api/v1/rules', {
						params: { query: { include_disabled: true, all_users: scope.query } }
					})
				),
				users.length > 0 ? users : unwrap(api.GET('/api/v1/users')),
				unwrap(api.GET('/api/v1/spaces', { params: { query: { all_users: scope.query } } }))
			]);
			// An earlier answer arriving late (the toggle switched twice) is dropped.
			if (current !== loads) return;
			[rules, users, spaces, problem] = [found, names, known, null];
		} catch (error) {
			if (current === loads) problem = describeError(error);
		}
	}

	// Again after a master data dialog saved (a title pattern's rule follows its type), and
	// when the scope setting changes.
	$effect(() => {
		void masterDataDialogs.changed;
		void scope.allUsers;
		untrack(() => void load());
	});

	async function switchRule(rule: Rule, enabled: boolean) {
		busy = rule.id;
		try {
			const changed = await unwrap(
				api.PATCH('/api/v1/rules/{id}', { params: { path: { id: rule.id } }, body: { enabled } })
			);
			rules = (rules ?? []).map((entry) => (entry.id === changed.id ? changed : entry));
			toast.success(enabled ? m.rule_switched_on() : m.rule_switched_off());
		} catch (error) {
			reportError(error);
		} finally {
			busy = null;
		}
	}
</script>

<svelte:head><title>{m.nav_rules()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.nav_rules()}>
		{#snippet actions()}
			<a
				href={kind === 'mail' ? `${BASE}/rules/mail/new` : `${BASE}/rules/new`}
				class={cn(buttonVariants())}
			>
				<Plus aria-hidden="true" />
				{m.rules_new()}
			</a>
		{/snippet}
	</PageHeader>

	{#if session.isAdmin}
		<Segmented
			label={m.rules_kind()}
			value={kind}
			options={[
				{ value: 'documents', label: m.rules_kind_documents(), count: rules?.length },
				{ value: 'mail', label: m.rules_kind_mail(), count: mailRules?.length }
			]}
			onchange={(value) => goto(value === 'mail' ? '?kind=mail' : '?')}
			class="self-start"
		/>
	{/if}

	{#if problem}
		<LoadProblem {problem} onretry={load} />
	{:else if kind === 'mail'}
		{#if mailRules}
			<MailRulesList bind:rules={mailRules} {mailboxes} {users} {spaces} {types} />
		{:else}
			<Loading />
		{/if}
	{:else if !rules}
		<Loading />
	{:else if rules.length === 0}
		<EmptyNote>{m.rules_none()}</EmptyNote>
	{:else}
		<ul class="flex flex-col gap-2">
			{#each rules as rule (rule.id)}
				<!-- The name's link takes the whole row; the switch and the pencil stand above it. -->
				<Card.Root as="li" size="row" class="relative flex flex-wrap items-center gap-3">
					<div class="flex min-w-0 flex-1 flex-col gap-1">
						<span class="flex flex-wrap items-center gap-2">
							<a
								href="{BASE}/rules/{rule.id}"
								class="truncate font-medium after:absolute after:inset-0 hover:underline"
								aria-label={m.rule_open({ name: rule.name })}>{rule.name}</a
							>
							<Badge variant="note">
								{placeName(rule)}
							</Badge>
							{#if rule.managed_by_document_type_id}
								<TitlePatternBadge
									documentTypeId={rule.managed_by_document_type_id}
									name={rule.name}
									ruleId={rule.id}
								/>
							{/if}
						</span>
						<span class="text-sm text-muted-foreground">
							{m.rule_priority_short({ priority: rule.priority })} ·
							{rule.triggers.map((trigger) => TRIGGER_LABELS[trigger]()).join(' · ')}
						</span>
						{#if rule.disabled_reason}
							<span class="text-sm text-destructive">
								{m.rule_disabled_reason({
									reason: reasonsText(rule.disabled_reasons, rule.disabled_reason) ?? ''
								})}
							</span>
						{/if}
					</div>
					{#if canChangeRule(rule, session.user, spaces)}
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
							href="{BASE}/rules/{rule.id}/edit"
						/>
					{:else}
						<Badge variant={rule.enabled ? 'green' : 'muted'}>
							{rule.enabled ? m.rule_on() : m.rule_off()}
						</Badge>
					{/if}
				</Card.Root>
			{/each}
		</ul>
	{/if}
</div>
