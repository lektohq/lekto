<script lang="ts">
	import Mail from '@lucide/svelte/icons/mail';
	import { untrack } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import DryRunGroup from '#lib/components/rules/DryRunGroup.svelte';
	import SelectionBar from '#lib/components/SelectionBar.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { formatDate } from '#lib/i18n.ts';
	import { loadMailRuleLookup, namesOf, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import {
		actionTexts,
		createBody,
		formOf,
		type DryRunMail,
		type MailRule
	} from '#lib/mail-rules.ts';
	import { folderLabel } from '#lib/mailboxes.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	// The dry run of a mail rule (Tobi, 05.11.2026: as the document rules'; web/DESIGN.md, "A
	// rule's dry run"): what the rule as it is stored would do with the mailbox's latest mails,
	// as Lekto recorded them; it reads only. The mails it would take stand in one group whose
	// head says what it does to them; mails its conditions hold for but a rule of higher priority
	// takes first stand last, a yellow group per such rule. Saved, the rule is paused: the bar
	// switches it on.
	const id = $derived(page.params.id ?? '');
	const saved = $derived(page.url.searchParams.has('saved'));
	let rule = $state<MailRule | null>(null);
	let lookup = $state<MailRuleLookup | null>(null);
	let mails = $state<DryRunMail[] | null>(null);
	let problem = $state<string | null>(null);
	let busy = $state(false);
	/** The groups folded away, by key. */
	const folded = new SvelteSet<string>();

	async function load(wanted: string) {
		problem = null;
		try {
			const [found, loaded] = await Promise.all([
				unwrap(api.GET('/api/v1/mail-rules/{id}', { params: { path: { id: wanted } } })),
				lookup ?? loadMailRuleLookup()
			]);
			[rule, lookup] = [found, loaded];
			mails = await unwrap(
				api.POST('/api/v1/mail-rules/dry-run', {
					body: { ...createBody(formOf(found)), rule_id: found.id }
				})
			);
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

	function fold(key: string) {
		if (!folded.delete(key)) folded.add(key);
	}

	const taken = $derived(mails?.filter((item) => item.decider === 'rule') ?? []);
	/** The mails a rule before it takes, by that rule. */
	const before = $derived.by(() => {
		const groups: Record<string, DryRunMail[]> = {};
		for (const item of mails ?? []) {
			if (item.decider !== 'other' || !item.matches) continue;
			const name = item.rule ?? '';
			groups[name] = [...(groups[name] ?? []), item];
		}
		return Object.entries(groups);
	});
	const conflicts = $derived(before.reduce((sum, [, items]) => sum + items.length, 0));
	const title = $derived(rule ? m.rule_apply_title({ name: rule.name }) : m.rule_apply_generic());
	const names = $derived(lookup ? namesOf(lookup) : null);
	const doing = $derived(rule && names ? actionTexts(rule, names) : []);

	const counted = (count: number) =>
		count === 1 ? m.mail_rule_mails_one() : m.mail_rule_mails({ count });
	const moment = (value: string) => formatDate(value, { dateStyle: 'medium', timeStyle: 'short' });
</script>

<svelte:head><title>{title} · {m.app_name()}</title></svelte:head>

{#snippet switcher()}
	<Switch
		bind:checked={() => rule?.enabled ?? false, switchRule}
		disabled={busy}
		aria-label={rule?.enabled
			? m.rule_switch_off({ name: rule.name })
			: m.rule_switch_on({ name: rule?.name ?? '' })}
	/>
{/snippet}

{#snippet bar()}
	<SelectionBar
		count={m.mail_rule_preview_count({ taken: taken.length, total: mails?.length ?? 0 })}
		{busy}
	>
		{#snippet hint()}
			{#if conflicts > 0}{m.mail_rule_preview_before({ count: conflicts })}{/if}
		{/snippet}
		{#snippet actions()}
			{#if rule && !rule.enabled}
				<Button size="sm" disabled={busy} onclick={() => void switchRule(true)}>
					{m.mail_rule_switch_on()}
				</Button>
			{/if}
		{/snippet}
	</SelectionBar>
{/snippet}

{#snippet row(item: DryRunMail)}
	<li class="flex items-start gap-3 px-4 py-2.5">
		<span
			class="flex h-12 w-9 shrink-0 items-center justify-center rounded-md border bg-muted text-muted-foreground"
			aria-hidden="true"><Mail class="size-4" /></span
		>
		<div class="flex min-w-0 flex-1 flex-col gap-1 text-sm">
			<span class="truncate text-base font-medium">{item.subject || m.mail_rule_no_subject()}</span>
			<span class="truncate text-muted-foreground">
				{[
					item.sender,
					moment(item.arrived_at),
					folderLabel(item.folder),
					item.attachments.length
						? m.mail_rule_dry_run_attachments({ count: item.attachments.length })
						: ''
				]
					.filter(Boolean)
					.join(' · ')}
			</span>
		</div>
	</li>
{/snippet}

<div class="flex flex-col gap-6">
	<PageHeader
		{title}
		back={{ href: `${BASE}/rules/mail/${id}`, label: rule?.name ?? m.nav_rules() }}
		actions={rule ? switcher : undefined}
		subtitle={saved ? m.mail_rule_saved_hint() : m.mail_rule_apply_hint()}
	/>

	{#if problem}
		<LoadProblem {problem} onretry={() => void load(id)} />
	{:else if !rule || !mails || !names}
		<Loading />
	{:else if mails.length === 0}
		<EmptyNote>{m.mail_rule_dry_run_none()}</EmptyNote>
	{:else}
		{#if !phone.current}{@render bar()}{/if}
		{#if taken.length === 0 && conflicts === 0}
			<EmptyNote>{m.mail_rule_preview_nothing({ count: mails.length })}</EmptyNote>
		{:else}
			<div class="flex flex-col gap-4">
				{#if taken.length > 0}
					<DryRunGroup
						label={counted(taken.length)}
						count={counted(taken.length)}
						open={!folded.has('rule')}
						onfold={() => fold('rule')}
					>
						{#snippet head()}
							{#each doing as text, index (index)}
								<span class="text-sm font-medium">{text}</span>
							{/each}
						{/snippet}
						{#each taken as item, index (index)}{@render row(item)}{/each}
					</DryRunGroup>
				{/if}
				{#each before as [name, items] (name)}
					<DryRunGroup
						label={counted(items.length)}
						count={counted(items.length)}
						conflict
						open={!folded.has(`before:${name}`)}
						onfold={() => fold(`before:${name}`)}
					>
						{#snippet head()}
							<Badge variant="yellow">{m.mail_rule_before({ name })}</Badge>
							<span class="text-sm text-muted-foreground">{m.mail_rule_before_hint()}</span>
						{/snippet}
						{#each items as item, index (index)}{@render row(item)}{/each}
					</DryRunGroup>
				{/each}
			</div>
		{/if}
		{#if phone.current}{@render bar()}{/if}
	{/if}
</div>
