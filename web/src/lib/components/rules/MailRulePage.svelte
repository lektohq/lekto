<script lang="ts">
	import Trash2 from '@lucide/svelte/icons/trash-2';
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
		createBody,
		formOf,
		patchBody,
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
	{/if}
</div>

<ConfirmDialog
	bind:open={removing}
	title={m.rule_delete({ name: rule?.name ?? '' })}
	description={m.mail_rule_delete_confirm()}
	confirmLabel={m.delete_title()}
	onconfirm={remove}
/>
