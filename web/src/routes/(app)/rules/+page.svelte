<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import MailRulesList from '#lib/components/rules/MailRulesList.svelte';
	import RuleListRow from '#lib/components/rules/RuleListRow.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import { loadMailRuleLookup, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import type { MailRule } from '#lib/mail-rules.ts';
	import { untrack } from 'svelte';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import { BASE } from '#lib/base.ts';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import TitlePatternBadge from '#lib/components/rules/TitlePatternBadge.svelte';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { buttonVariants } from '#lib/components/ui/button/index.ts';
	import { describeError } from '#lib/errors.ts';
	import type { Space, UserName } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonsText } from '#lib/reasons.ts';
	import { scope } from '#lib/scope.svelte.ts';
	import { canChangeRule } from '#lib/permissions.ts';
	import { TRIGGER_LABELS } from '#lib/rules/describe.ts';
	import { switchRule } from '#lib/rules/switch.ts';
	import { placeLabel, placeOf } from '#lib/rules/places.ts';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import Loading from '#lib/components/Loading.svelte';

	type Rule = components['schemas']['RuleOut'];

	// The rules of the documents, and for admins the mail rules beside them (Tobi, 04.11.2026;
	// mock D): a `Segmented` "Dokumente | Mails" with their counts; the choice stands in the URL.
	const kind = $derived(
		session.isAdmin && page.url.searchParams.get('kind') === 'mail' ? 'mail' : 'documents'
	);
	let mailRules = $state<MailRule[] | null>(null);
	// What a mail rule names (every space: admins read them all, whoever is a member).
	let mailLookup = $state<MailRuleLookup | null>(null);

	async function loadMail() {
		if (!session.isAdmin) return;
		try {
			[mailRules, mailLookup] = await Promise.all([
				unwrap(api.GET('/api/v1/mail-rules')),
				loadMailRuleLookup()
			]);
		} catch (error) {
			problem = describeError(error);
		}
	}

	function retry() {
		problem = null;
		void load();
		void loadMail();
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

	async function switchOne(rule: Rule, enabled: boolean) {
		busy = rule.id;
		const changed = await switchRule(rule.id, enabled);
		if (changed) rules = (rules ?? []).map((entry) => (entry.id === changed.id ? changed : entry));
		busy = null;
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
		<LoadProblem {problem} onretry={retry} />
	{:else if kind === 'mail'}
		{#if mailRules && mailLookup}
			<MailRulesList bind:rules={mailRules} lookup={mailLookup} />
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
				<RuleListRow
					href="{BASE}/rules/{rule.id}"
					editHref="{BASE}/rules/{rule.id}/edit"
					name={rule.name}
					enabled={rule.enabled}
					canChange={canChangeRule(rule, session.user, spaces)}
					busy={busy === rule.id}
					disabledReason={rule.disabled_reason
						? (reasonsText(rule.disabled_reasons, rule.disabled_reason) ?? '')
						: null}
					onswitch={(enabled) => switchOne(rule, enabled)}
				>
					{#snippet badges()}
						<Badge variant="note">{placeName(rule)}</Badge>
						{#if rule.managed_by_document_type_id}
							<TitlePatternBadge
								documentTypeId={rule.managed_by_document_type_id}
								name={rule.name}
								ruleId={rule.id}
							/>
						{/if}
					{/snippet}
					{#snippet summary()}
						{m.rule_priority_short({ priority: rule.priority })} ·
						{rule.triggers.map((trigger) => TRIGGER_LABELS[trigger]()).join(' · ')}
					{/snippet}
				</RuleListRow>
			{/each}
		</ul>
	{/if}
</div>
