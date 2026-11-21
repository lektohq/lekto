<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Minus from '@lucide/svelte/icons/minus';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { TOKEN_NAME_MAX, tokenChanges, tokensChanged } from '#lib/tokens.svelte.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import EditorShell from '#lib/components/EditorShell.svelte';
	import FormDialog from '#lib/components/FormDialog.svelte';
	import Select from '#lib/components/Select.svelte';
	import SecretDialog from '#lib/components/SecretDialog.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { describeError } from '#lib/errors.ts';
	import { isoDayLocal } from '#lib/dates.ts';
	import { formatDate } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import Loading from '#lib/components/Loading.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import DateInput from '#lib/components/DateInput.svelte';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import { session } from '#lib/session.svelte.ts';
	import {
		ADMIN_RIGHTS,
		AREAS,
		type AdminRight,
		type Area,
		type Right,
		type Verb
	} from '#lib/token-rights.ts';

	type Token = components['schemas']['TokenOut'];
	type Scope = components['schemas']['TokenScope'];

	// API tokens: for scripts and tools, never for this UI. The token itself is shown once.
	let tokens = $state<Token[] | null>(null);
	let problem = $state<string | null>(null);
	let creating = $state(false);
	// Where the focus goes once a token's secret was seen, or its row is gone with it: the
	// dialogs before have closed, and the keyboard would start at the top of the page.
	let newToken = $state<HTMLElement | null>(null);
	let name = $state('');
	// A preset, or the rights one by one (`own`; `.knowledge/plans/token-rights.md`).
	let scope = $state<Scope | 'own'>('read');
	let rights = $state<Right[]>([]);
	let expires = $state('');
	let created = $state<string | null>(null);
	// The token whose dialog is open (web/DESIGN.md, "Settings").
	let shown = $state<Token | null>(null);

	async function load() {
		problem = null;
		try {
			tokens = await unwrap(api.GET('/api/v1/auth/tokens'));
		} catch (failure) {
			problem = describeError(failure);
		}
	}

	// Again whenever a token is created or revoked here or on the shortcut's card.
	$effect(() => {
		void tokenChanges.version;
		void load();
	});

	function openCreate() {
		name = '';
		scope = 'read';
		rights = [];
		expires = '';
		creating = true;
	}

	async function create() {
		const token = await unwrap(
			api.POST('/api/v1/auth/tokens', {
				body: {
					name: name.trim(),
					...(scope === 'own' ? { rights } : { scope }),
					// The token works through the end of the chosen day, in this browser's zone.
					expires_at: expires ? new Date(`${expires}T23:59:59`).toISOString() : null
				}
			})
		);
		created = token.token;
		tokensChanged();
	}

	async function revoke() {
		if (!shown) return;
		await unwrap(api.DELETE('/api/v1/auth/tokens/{id}', { params: { path: { id: shown.id } } }));
		shown = null;
		toast.success(m.token_revoked());
		tokensChanged();
		// After the dialog has given the focus back to a row that is gone.
		setTimeout(() => newToken?.focus(), 0);
	}

	// The scope `upload` is for a shortcut that sends shared files (web/DESIGN.md, "App").
	const SCOPE_LABELS: Record<Scope, () => string> = {
		read: m.token_scope_read,
		read_write: m.token_scope_read_write,
		upload: m.token_scope_upload
	};
	const scopes = [
		...(['read', 'read_write', 'upload'] as const).map((value) => ({
			value,
			label: SCOPE_LABELS[value]()
		})),
		{ value: 'own', label: m.token_scope_own() }
	];
	const AREA_LABELS: Record<Area, () => string> = {
		documents: m.token_area_documents,
		master_data: m.token_area_master_data,
		rules: m.token_area_rules,
		spaces: m.token_area_spaces,
		webhooks: m.token_area_webhooks,
		lenses: m.token_area_lenses,
		push: m.token_area_push,
		system: m.token_area_system
	};
	const VERB_LABELS: Record<Verb, () => string> = {
		count: m.token_verb_count,
		read: m.token_verb_read,
		write: m.token_verb_write,
		upload: m.token_verb_upload
	};
	const ADMIN_LABELS: Record<AdminRight, () => string> = {
		'admin:count_all': m.token_right_admin_count_all,
		'admin:documents_all': m.token_right_admin_documents_all,
		'admin:mailboxes': m.token_right_admin_mailboxes,
		'admin:private_webhooks': m.token_right_admin_private_webhooks,
		'admin:manage': m.token_right_admin_manage
	};

	function used(token: Token): string {
		return token.last_used_at
			? formatDate(token.last_used_at, { dateStyle: 'short', timeStyle: 'short' })
			: m.token_never_used();
	}
	function expiry(token: Token): string {
		return token.expires_at
			? formatDate(token.expires_at, { dateStyle: 'short' })
			: m.token_no_expiry();
	}
	const today = isoDayLocal(new Date());
</script>

<Card.Root>
	<Card.Header>
		<Card.Title>{m.token_title()}</Card.Title>
		<Card.Description>{m.token_hint()}</Card.Description>
		<Card.Action>
			<Button bind:ref={newToken} onclick={openCreate}>{m.token_new()}</Button>
		</Card.Action>
	</Card.Header>
	<Card.Content>
		{#if problem}
			<LoadProblem {problem} onretry={load} />
		{:else if tokens === null}
			<Loading />
		{:else if tokens.length === 0}
			<p class="text-muted-foreground">{m.token_none()}</p>
		{:else}
			<ul class="divide-y">
				{#each tokens as token (token.id)}
					<!-- The name opens the token's dialog, with its rights and "Widerrufen". -->
					<li class="relative flex items-center gap-3 py-3">
						<div class="min-w-0 flex-1">
							<button
								type="button"
								class="block max-w-full truncate text-left font-medium after:absolute after:inset-0 hover:text-brand"
								onclick={() => (shown = token)}
							>
								{token.name}
							</button>
							<p class="text-sm text-muted-foreground">
								{token.last_used_at ? m.token_used({ time: used(token) }) : m.token_never_used()}
								·
								{token.expires_at ? m.token_expires({ time: expiry(token) }) : m.token_no_expiry()}
							</p>
						</div>
						<Badge variant="note">
							{token.scope
								? SCOPE_LABELS[token.scope]()
								: m.token_scope_custom({ count: token.rights.length })}
						</Badge>
						<ChevronRight class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
					</li>
				{/each}
			</ul>
		{/if}
	</Card.Content>
</Card.Root>

<FormDialog
	bind:open={creating}
	title={m.token_new()}
	submitLabel={m.create()}
	disabled={name.trim() === '' || (scope === 'own' && rights.length === 0)}
	action={create}
>
	<Field.Field>
		<Field.Label for="token-name">{m.field_name()}</Field.Label>
		<Input id="token-name" bind:value={name} maxlength={TOKEN_NAME_MAX} required />
	</Field.Field>
	<Field.Field>
		<Field.Label for="token-scope">{m.token_scope()}</Field.Label>
		<Select
			id="token-scope"
			value={scope}
			onchange={(value) => (scope = value as Scope | 'own')}
			options={scopes}
		/>
		<Field.Description>{m.token_scope_hint()}</Field.Description>
	</Field.Field>
	{#if scope === 'own'}
		<!-- The rights one by one, by area; the admin rights only for an admin. -->
		<fieldset class="flex flex-col gap-3">
			<legend class="mb-2 text-sm font-medium">{m.token_rights()}</legend>
			{#each AREAS as { area, rights: own } (area)}
				<fieldset class="flex flex-wrap items-center gap-x-4 gap-y-2">
					<legend class="mb-1 w-full text-sm text-muted-foreground">{AREA_LABELS[area]()}</legend>
					{#each own as [right, verb] (right)}
						<Choice value={right} bind:group={rights}>{VERB_LABELS[verb]()}</Choice>
					{/each}
				</fieldset>
			{/each}
			<p class="text-sm text-muted-foreground">{m.token_rights_hint()}</p>
		</fieldset>
		{#if session.isAdmin}
			<fieldset class="flex flex-col gap-2">
				<legend class="mb-2 text-sm font-medium">{m.token_admin_rights()}</legend>
				{#each ADMIN_RIGHTS as right (right)}
					<Choice value={right} bind:group={rights}>{ADMIN_LABELS[right]()}</Choice>
				{/each}
				<p class="text-sm text-muted-foreground">{m.token_admin_rights_hint()}</p>
			</fieldset>
		{/if}
	{/if}
	<Field.Field>
		<Field.Label for="token-expires">{m.token_expires_on()}</Field.Label>
		<DateInput id="token-expires" label={m.token_expires_on()} min={today} bind:value={expires} />
		<Field.Description>{m.token_expires_hint()}</Field.Description>
	</Field.Field>
</FormDialog>

<SecretDialog
	secret={created}
	title={m.token_created_title()}
	description={m.token_created_hint()}
	onclose={() => (created = null)}
	returnTo={newToken}
/>

{#if shown}
	{@const token = shown}
	{@const held = new Set(token.rights)}
	<EditorShell
		bind:open={() => shown !== null, (open) => !open && (shown = null)}
		title={token.name}
		shortTitle={m.token_one()}
		description={m.token_dialog_hint()}
		size="md"
		ondelete={revoke}
		deleteTitle={m.token_revoke_named({ name: token.name })}
		deleteDescription={m.token_revoke_confirm()}
		deleteLabel={m.token_revoke()}
	>
		<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
			<dt class="text-muted-foreground">{m.token_fact_created()}</dt>
			<dd class="tabular-nums">{formatDate(token.created_at, { dateStyle: 'short' })}</dd>
			<dt class="text-muted-foreground">{m.token_fact_used()}</dt>
			<dd class="tabular-nums">{used(token)}</dd>
			<dt class="text-muted-foreground">{m.token_fact_expiry()}</dt>
			<dd class="tabular-nums">{expiry(token)}</dd>
		</dl>
		<section class="flex flex-col gap-2" aria-labelledby="token-rights">
			<h3 id="token-rights" class="flex items-center gap-2 text-sm font-medium">
				{m.token_rights()}
				<Badge variant="note">
					{token.scope ? SCOPE_LABELS[token.scope]() : m.token_scope_own()}
				</Badge>
			</h3>
			<ul class="divide-y rounded-xl border">
				{#each AREAS as { area, rights: own } (area)}
					<li class="grid gap-1 px-3 py-2 text-sm sm:grid-cols-[9.5rem_1fr] sm:gap-3">
						<span class="text-muted-foreground">{AREA_LABELS[area]()}</span>
						<span class="flex flex-wrap gap-x-3.5 gap-y-1">
							{#each own as [right, verb] (right)}
								{@render mark(held.has(right), VERB_LABELS[verb]())}
							{/each}
						</span>
					</li>
				{/each}
			</ul>
		</section>
		{#if session.isAdmin}
			<section class="flex flex-col gap-2" aria-labelledby="token-admin-rights">
				<h3 id="token-admin-rights" class="text-sm font-medium">{m.token_admin_rights()}</h3>
				<ul class="flex flex-col gap-1.5 rounded-xl border px-3 py-2.5 text-sm">
					{#each ADMIN_RIGHTS as right (right)}
						<li>{@render mark(held.has(right), ADMIN_LABELS[right]())}</li>
					{/each}
				</ul>
				<p class="text-sm text-muted-foreground">{m.token_admin_rights_hint()}</p>
			</section>
		{/if}
	</EditorShell>
{/if}

<!-- A right shown, held or not: the mark and the word, never the colour alone. -->
{#snippet mark(on: boolean, label: string)}
	<span class={['inline-flex items-center gap-1.5', !on && 'text-muted-foreground']}>
		{#if on}
			<Check class="size-4 shrink-0 text-primary" aria-hidden="true" />
		{:else}
			<Minus class="size-4 shrink-0" aria-hidden="true" />
		{/if}
		{label}
		<span class="sr-only">{on ? m.token_right_held() : m.token_right_not_held()}</span>
	</span>
{/snippet}
