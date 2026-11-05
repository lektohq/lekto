<script lang="ts">
	import PlugZap from '@lucide/svelte/icons/plug-zap';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import DateInput from '#lib/components/DateInput.svelte';
	import EditorShell from '#lib/components/EditorShell.svelte';
	import HintLabel from '#lib/components/HintLabel.svelte';
	import MultiPicker from '#lib/components/MultiPicker.svelte';
	import SearchSelect from '#lib/components/SearchSelect.svelte';
	import Select from '#lib/components/Select.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { isoDayLocal } from '#lib/dates.ts';
	import { formatDate } from '#lib/i18n.ts';
	import {
		complete,
		createBody,
		folderLabel,
		formOf,
		intervalOptions,
		NOTHING,
		patchBody,
		portAfter,
		type ConnectionTest,
		type FetchStart,
		type Mailbox,
		type MailboxForm,
		type MailSecurity
	} from '#lib/mailboxes.ts';
	import { userChoice, type DocumentType, type UserName } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';

	// The dialog of a mailbox (Tobi, 04.11.2026; mock D) in two parts (Tobi, 05.11.2026):
	// "Verbindung", where Lekto signs in and the test of the connection that lists the folders,
	// and "Abruf": the folders to pick from, then two rows of two: how often and what a mail no
	// rule takes brings in, which mails it fetches and the type of a mail's text. A new mailbox starts at the connection
	// and goes on to the fetching once a test found the folders. One save stores both parts. The
	// password is never shown again: left empty, the stored one stays. Deleting is in the footer.
	let {
		open = $bindable(false),
		mailbox,
		onsaved
	}: {
		open?: boolean;
		/** The mailbox to change; null for a new one. */
		mailbox: Mailbox | null;
		onsaved: () => Promise<void> | void;
	} = $props();

	let form = $state<MailboxForm>(formOf(null));
	let users = $state<UserName[]>([]);
	let types = $state<DocumentType[]>([]);
	let testing = $state(false);
	let tested = $state<ConnectionTest | null>(null);
	let testProblem = $state<string | null>(null);
	let part = $state<'connection' | 'fetch'>('connection');

	const PARTS = [
		{ value: 'connection', label: m.mailbox_part_connection() },
		{ value: 'fetch', label: m.mailbox_part_fetch() }
	];

	const creating = $derived(mailbox === null);
	const title = $derived(
		mailbox ? m.mailbox_edit_title({ name: mailbox.name }) : m.mailbox_new_title()
	);

	$effect(() => {
		if (!open) return;
		form = formOf(mailbox);
		part = 'connection';
		tested = null;
		testProblem = null;
		void loadChoices();
	});

	async function loadChoices() {
		try {
			[users, types] = await Promise.all([
				unwrap(api.GET('/api/v1/users')),
				unwrap(api.GET('/api/v1/document-types'))
			]);
		} catch (error) {
			testProblem = describeError(error);
		}
	}

	const SECURITIES: { value: MailSecurity; label: string }[] = [
		{ value: 'tls', label: m.mail_security_tls() },
		{ value: 'starttls', label: m.mail_security_starttls() },
		{ value: 'none', label: m.mail_security_none() }
	];

	// Which mails, in one choice (Tobi, 05.11.2026): from the day of setting up (a new mailbox:
	// today), from a day picked under it, or every unread one, however old.
	const STARTS = $derived([
		{
			value: 'since_setup',
			label: mailbox
				? m.mail_start_since_setup({ day: formatDate(mailbox.created_at) })
				: m.mail_start_since_today()
		},
		{ value: 'since_date', label: m.mail_start_since_date() },
		{ value: 'unread', label: m.mail_start_unread() }
	]);

	const fallbacks = $derived([
		{ value: NOTHING, label: m.mail_fallback_nothing() },
		...users
			.filter((user) => user.active || user.id === form.fallback)
			.map((user) => ({
				value: user.id,
				label: m.mail_fallback_everything({ name: userChoice(user) })
			}))
	]);

	/** The folders to pick from: those the test found, and those chosen already. */
	const folders = $derived(
		[...new Set([...(tested?.folders ?? []), ...form.folders])].map((name) => ({
			value: name,
			label: folderLabel(name)
		}))
	);

	/** A day to start from begins at the day of setting up (a new mailbox: today). */
	function startChanged(value: string) {
		form.start = value as FetchStart;
		if (form.start === 'since_date' && form.since === '') {
			form.since = isoDayLocal(mailbox ? new Date(mailbox.created_at) : new Date());
		}
	}

	function securityChanged(value: string) {
		const security = value as MailSecurity;
		form.port = portAfter(form, security);
		form.security = security;
	}

	async function test() {
		testing = true;
		tested = null;
		testProblem = null;
		try {
			tested = await unwrap(
				api.POST('/api/v1/mailboxes/test', {
					body: {
						host: form.host.trim(),
						port: Number(form.port),
						security: form.security,
						username: form.username.trim(),
						...(form.password ? { password: form.password } : {}),
						...(mailbox && !form.password ? { mailbox_id: mailbox.id } : {})
					}
				})
			);
			// A new mailbox goes on to its folders once the test found them.
			if (creating && !tested.error) part = 'fetch';
		} catch (error) {
			testProblem = describeError(error);
		} finally {
			testing = false;
		}
	}

	const testable = $derived(
		form.host.trim() !== '' &&
			form.username.trim() !== '' &&
			form.port !== '' &&
			(form.password !== '' || !creating)
	);

	let fetching = $state(false);

	/** The next fetch at once (a stored mailbox that is not paused). */
	async function fetchNow() {
		if (!mailbox) return;
		fetching = true;
		try {
			await unwrap(
				api.POST('/api/v1/mailboxes/{id}/fetch', { params: { path: { id: mailbox.id } } })
			);
			toast.success(m.mailbox_fetch_queued());
		} catch (error) {
			reportError(error);
		} finally {
			fetching = false;
		}
	}

	async function save() {
		if (mailbox) {
			await unwrap(
				api.PATCH('/api/v1/mailboxes/{id}', {
					params: { path: { id: mailbox.id } },
					body: patchBody(form)
				})
			);
		} else {
			await unwrap(api.POST('/api/v1/mailboxes', { body: createBody(form) }));
		}
		await onsaved();
	}

	async function remove() {
		if (!mailbox) return;
		await unwrap(api.DELETE('/api/v1/mailboxes/{id}', { params: { path: { id: mailbox.id } } }));
		open = false;
		await onsaved();
	}
</script>

<EditorShell
	bind:open
	{title}
	shortTitle={m.mailbox_short()}
	submitLabel={creating ? m.create() : m.save()}
	disabled={!complete(form, creating)}
	action={save}
	ondelete={mailbox ? remove : undefined}
	deleteTitle={mailbox ? m.mailbox_delete_title({ name: mailbox.name }) : ''}
	deleteDescription={m.mailbox_delete_description()}
	tabs={PARTS}
	bind:tab={() => part, (value) => (part = value as 'connection' | 'fetch')}
	class="h-[min(46.25rem,calc(100dvh-2rem))]"
>
	<div class={['flex flex-col gap-4', part !== 'connection' && 'hidden']}>
		<Field.Field>
			<Field.Label for="mailbox-name">{m.field_name()}</Field.Label>
			<Input id="mailbox-name" bind:value={form.name} maxlength={100} required />
		</Field.Field>
		<div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_6rem_10rem]">
			<Field.Field>
				<Field.Label for="mailbox-host">{m.mail_host()}</Field.Label>
				<Input
					id="mailbox-host"
					bind:value={form.host}
					maxlength={255}
					autocomplete="off"
					spellcheck={false}
					placeholder={m.mail_host_placeholder()}
				/>
			</Field.Field>
			<Field.Field>
				<Field.Label for="mailbox-port">{m.mail_port()}</Field.Label>
				<Input id="mailbox-port" bind:value={form.port} inputmode="numeric" maxlength={5} />
			</Field.Field>
			<Field.Field>
				<HintLabel for="mailbox-security" label={m.mail_security()} hint={m.mail_security_hint()} />
				<Select
					id="mailbox-security"
					value={form.security}
					options={SECURITIES}
					onchange={securityChanged}
				/>
			</Field.Field>
		</div>
		<div class="grid gap-4 sm:grid-cols-2">
			<Field.Field>
				<Field.Label for="mailbox-username">{m.mail_username()}</Field.Label>
				<Input
					id="mailbox-username"
					bind:value={form.username}
					maxlength={320}
					autocomplete="off"
					spellcheck={false}
				/>
			</Field.Field>
			<Field.Field>
				<HintLabel for="mailbox-password" label={m.mail_password()} hint={m.mail_password_hint()} />
				<Input
					id="mailbox-password"
					type="password"
					bind:value={form.password}
					maxlength={1000}
					autocomplete="new-password"
					placeholder={creating ? undefined : m.mail_password_stored()}
					aria-describedby={creating ? undefined : 'mailbox-password-note'}
				/>
				{#if !creating}
					<Field.Description id="mailbox-password-note">{m.mail_password_keep()}</Field.Description>
				{/if}
			</Field.Field>
		</div>
		<div class="flex flex-wrap items-center gap-3">
			<Button type="button" variant="outline" disabled={!testable || testing} onclick={test}>
				<PlugZap aria-hidden="true" />
				{m.mail_test()}
			</Button>
			{#if mailbox?.enabled}
				<Button type="button" variant="outline" disabled={fetching} onclick={fetchNow}>
					<RefreshCw aria-hidden="true" />
					{m.mailbox_fetch()}
				</Button>
			{/if}
			<p role="status" class="text-sm">
				{#if testing}
					<span class="text-muted-foreground">{m.mail_testing()}</span>
				{:else if testProblem}
					<span class="text-destructive">{testProblem}</span>
				{:else if tested?.error}
					<span class="text-destructive">{reasonText(tested.error)}</span>
				{:else if tested}
					<span class="text-lane-green-foreground"
						>{m.mail_test_ok({ count: tested.folders.length })}</span
					>
					{#if !tested.own_keywords}
						<span class="text-muted-foreground">{m.mail_test_no_own_keywords()}</span>
					{/if}
				{/if}
			</p>
		</div>
	</div>
	<div class={['flex flex-col gap-4', part !== 'fetch' && 'hidden']}>
		<Field.Field>
			<HintLabel id="mailbox-folders-label" label={m.mail_folders()} hint={m.mail_folders_hint()} />
			<MultiPicker
				id="mailbox-folders"
				label={m.mail_folders()}
				options={folders}
				selected={form.folders}
				onchange={(chosen) => (form.folders = chosen)}
			/>
			{#if !tested}
				<Field.Description>{m.mail_folders_test_first()}</Field.Description>
			{/if}
		</Field.Field>
		<div class="grid gap-4 sm:grid-cols-2">
			<Field.Field>
				<Field.Label for="mailbox-interval">{m.mail_interval()}</Field.Label>
				<Select
					id="mailbox-interval"
					bind:value={form.interval}
					options={intervalOptions(Number(form.interval))}
				/>
			</Field.Field>
			<Field.Field>
				<HintLabel for="mailbox-fallback" label={m.mail_fallback()} hint={m.mail_fallback_hint()} />
				<Select id="mailbox-fallback" bind:value={form.fallback} options={fallbacks} />
			</Field.Field>
			<Field.Field>
				<HintLabel for="mailbox-start" label={m.mail_start()} hint={m.mail_start_hint()} />
				<Select id="mailbox-start" value={form.start} options={STARTS} onchange={startChanged} />
				{#if form.start === 'since_date'}
					<DateInput label={m.mail_start_day()} bind:value={form.since} />
				{/if}
			</Field.Field>
			<Field.Field>
				<HintLabel
					for="mailbox-body-type"
					label={m.mail_body_type()}
					hint={m.mail_body_type_hint()}
				/>
				<SearchSelect
					id="mailbox-body-type"
					title={m.picker_title_type()}
					bind:value={form.bodyTypeId}
					options={types.map((entry) => ({ value: entry.id, label: entry.name }))}
					placeholder={m.mail_body_type_open()}
					noneLabel={m.mail_body_type_open()}
				/>
			</Field.Field>
		</div>
	</div>
</EditorShell>
