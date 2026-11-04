<script lang="ts">
	import Play from '@lucide/svelte/icons/play';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import { formatDate } from '#lib/i18n.ts';
	import { folderLabel } from '#lib/mailboxes.ts';
	import { onMount } from 'svelte';
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
	import MailRuleForm from '#lib/components/rules/MailRuleForm.svelte';
	import UnsavedGuard from '#lib/components/UnsavedGuard.svelte';
	import { describeError } from '#lib/errors.ts';
	import {
		complete,
		createBody,
		formOf,
		patchBody,
		type DryRunMail,
		type MailRule,
		type MailRuleForm as Form
	} from '#lib/mail-rules.ts';
	import type { Mailbox } from '#lib/mailboxes.ts';
	import type { DocumentType, Space, UserName } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A mail rule's page (Tobi, 04.11.2026; mock E): the editor of a new one (`id` null; the
	// mailbox from `?mailbox=`, its type of the mail text proposed) or of a stored one, with
	// its delete in the head. Saving goes back to the rules' Mails.
	let { id }: { id: string | null } = $props();

	const back = `${BASE}/rules?kind=mail`;
	let rule = $state<MailRule | null>(null);
	let form = $state<Form | null>(null);
	let initial = '';
	let mailboxes = $state<Mailbox[]>([]);
	let users = $state<UserName[]>([]);
	let spaces = $state<Space[]>([]);
	let types = $state<DocumentType[]>([]);
	let problem = $state<string | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let leaving = $state(false);
	let removing = $state(false);

	const changed = $derived(form !== null && JSON.stringify(form) !== initial);

	async function load() {
		problem = null;
		try {
			const [boxes, people, places, kinds, stored] = await Promise.all([
				unwrap(api.GET('/api/v1/mailboxes')),
				unwrap(api.GET('/api/v1/users')),
				unwrap(api.GET('/api/v1/spaces', { params: { query: { all_users: true } } })),
				unwrap(api.GET('/api/v1/document-types')),
				id ? unwrap(api.GET('/api/v1/mail-rules/{id}', { params: { path: { id } } })) : null
			]);
			[mailboxes, users, spaces, types, rule] = [boxes, people, places, kinds, stored];
			const wanted = page.url.searchParams.get('mailbox');
			const mailbox = boxes.find((entry) => entry.id === wanted) ?? boxes[0];
			form = formOf(stored, mailbox?.id ?? '', mailbox?.body_type_id ?? '');
			initial = JSON.stringify(form);
		} catch (failure) {
			problem = describeError(failure);
		}
	}

	onMount(load);

	async function save() {
		if (!form) return;
		busy = true;
		error = null;
		try {
			if (id) {
				await unwrap(
					api.PATCH('/api/v1/mail-rules/{id}', {
						params: { path: { id } },
						body: patchBody(form)
					})
				);
			} else {
				await unwrap(api.POST('/api/v1/mail-rules', { body: createBody(form) }));
			}
			toast.success(m.mail_rule_saved());
			leaving = true;
			await goto(back);
		} catch (failure) {
			error = describeError(failure);
		} finally {
			busy = false;
		}
	}

	// The dry run (Tobi, 04.11.2026; plan PR 5): what the rule as the form holds it would do
	// with the mailbox's latest mails, as Lekto recorded them; reads only.
	let dry = $state<DryRunMail[] | null>(null);
	let trying = $state(false);
	const taken = $derived(dry?.filter((item) => item.decider === 'rule').length ?? 0);

	async function tryRule() {
		if (!form) return;
		trying = true;
		error = null;
		try {
			dry = await unwrap(
				api.POST('/api/v1/mail-rules/dry-run', {
					body: { ...createBody(form), rule_id: id }
				})
			);
		} catch (failure) {
			error = describeError(failure);
		} finally {
			trying = false;
		}
	}

	const moment = (value: string) => formatDate(value, { dateStyle: 'medium', timeStyle: 'short' });

	async function remove() {
		if (!id) return;
		await unwrap(api.DELETE('/api/v1/mail-rules/{id}', { params: { path: { id } } }));
		toast.success(m.rule_deleted());
		leaving = true;
		await goto(back);
	}

	const title = $derived(id ? (rule?.name ?? m.mail_rule_generic()) : m.mail_rule_new_title());
</script>

<svelte:head><title>{title} · {m.nav_rules()} · {m.app_name()}</title></svelte:head>

<UnsavedGuard dirty={changed && !leaving} />

<div class="flex flex-col gap-6">
	<PageHeader {title} back={{ href: back, label: m.nav_rules() }}>
		{#snippet actions()}
			{#if rule}
				<IconButton label={m.rule_delete({ name: rule.name })} onclick={() => (removing = true)}>
					<Trash2 aria-hidden="true" />
				</IconButton>
			{/if}
		{/snippet}
	</PageHeader>

	{#if problem}
		<LoadProblem {problem} onretry={load} />
	{:else if !form}
		<Loading />
	{:else}
		<MailRuleForm
			{form}
			{mailboxes}
			{users}
			{spaces}
			{types}
			{busy}
			{error}
			cancelHref={back}
			onsubmit={save}
		/>
		<section class="flex flex-col gap-3" aria-labelledby="mail-rule-dry-run">
			<div class="flex flex-wrap items-center justify-between gap-2">
				<SectionTitle id="mail-rule-dry-run">{m.mail_rule_dry_run()}</SectionTitle>
				<Button variant="outline" disabled={trying || !complete(form)} onclick={tryRule}>
					<Play aria-hidden="true" />
					{m.mail_rule_dry_run()}
				</Button>
			</div>
			{#if dry === null}
				<p class="text-sm text-muted-foreground">{m.mail_rule_dry_run_hint()}</p>
			{:else if dry.length === 0}
				<p class="text-sm text-muted-foreground">{m.mail_rule_dry_run_none()}</p>
			{:else}
				<p class="text-sm" role="status">
					{m.mail_rule_dry_run_count({ taken, count: dry.length })}
				</p>
				<ul class="flex flex-col gap-2">
					{#each dry as item, index (index)}
						<Card.Root as="li" size="row" class="flex flex-wrap items-center gap-3">
							<div class="flex min-w-0 flex-1 flex-col gap-1">
								<span class="truncate font-medium">{item.subject || m.mail_rule_no_subject()}</span>
								<span class="truncate text-sm text-muted-foreground">
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
							{#if item.decider === 'rule'}
								<Badge variant="primary">{m.mail_rule_decider_rule()}</Badge>
							{:else if item.decider === 'other'}
								<Badge variant="muted">{m.mail_rule_decider_other({ name: item.rule ?? '' })}</Badge
								>
							{:else if item.decider === 'fallback'}
								<Badge variant="note">{m.mail_rule_decider_fallback()}</Badge>
							{:else}
								<Badge variant="muted">{m.mail_rule_decider_nothing()}</Badge>
							{/if}
						</Card.Root>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}
</div>

<ConfirmDialog
	bind:open={removing}
	title={m.rule_delete({ name: rule?.name ?? '' })}
	description={m.mail_rule_delete_confirm()}
	confirmLabel={m.delete_title()}
	onconfirm={remove}
/>
