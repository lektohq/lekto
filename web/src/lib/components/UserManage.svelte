<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import ProfileForm from '#lib/components/ProfileForm.svelte';
	import Select from '#lib/components/Select.svelte';
	import UserDeleteDialog from '#lib/components/UserDeleteDialog.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { userLabel } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import Segmented from '#lib/components/Segmented.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import { loadProfile, type Profile, type ProfileData } from '#lib/profile.ts';

	type Account = components['schemas']['AccountOut'];
	type Role = components['schemas']['Role'];

	// Everything an admin does with one account. Own account: no password reset, no removal of the
	// second factor (the API refuses both; there are the settings for that). In parts as the
	// settings have them (Tobi, 02.11.2026): the account, the profile, the identifiers at
	// contacts; each keeps what was typed while another shows, and the body scrolls across the
	// dialog's width, its title and parts staying.
	let {
		open = $bindable(false),
		userId,
		onchanged
	}: { open?: boolean; userId: string; onchanged: () => void } = $props();

	let account = $state<Account | null>(null);
	let problem = $state<string | null>(null);
	let busy = $state(false);
	let password = $state('');
	let revoke = $state(false);
	let resetError = $state<string | null>(null);
	let confirm = $state<'totp' | 'oidc' | null>(null);
	let deleting = $state(false);
	let profile = $state<ProfileData | null>(null);
	let profileProblem = $state<string | null>(null);
	let part = $state<'account' | 'profile' | 'identifiers'>('account');
	let scroller = $state<HTMLElement | null>(null);
	const parts = $derived([
		{ value: 'account', label: m.user_tab_account() },
		{ value: 'profile', label: m.profile_title(), hint: m.profile_hint() },
		{
			value: 'identifiers',
			label: m.profile_numbers(),
			count: profile ? profile.profile.numbers.length : undefined
		}
	]);

	$effect(() => {
		void part;
		if (scroller) scroller.scrollTop = 0;
	});

	const own = $derived(account?.id === session.user?.id);

	async function load(initial = false) {
		// After a change the dialog keeps showing the account until the new state arrives.
		if (initial) account = null;
		problem = null;
		try {
			const data = await unwrap(
				api.GET('/api/v1/users/{id}', { params: { path: { id: userId } } })
			);
			if ('has_password' in data) account = data;
			else problem = m.error_forbidden();
		} catch (error) {
			problem = describeError(error);
		}
	}

	function profileSaved(changed: Profile) {
		if (profile) profile.profile = changed;
		onchanged();
	}

	async function loadProfileData() {
		profileProblem = null;
		try {
			profile = await loadProfile(userId);
		} catch (error) {
			profileProblem = describeError(error);
		}
	}

	$effect(() => {
		if (open) {
			password = '';
			revoke = false;
			resetError = null;
			part = 'account';
			profile = null;
			void load(true);
			void loadProfileData();
		}
	});

	async function run(action: () => Promise<unknown>, done: string) {
		busy = true;
		try {
			await action();
			toast.success(done);
			onchanged();
			await load();
		} catch (error) {
			reportError(error);
		} finally {
			busy = false;
		}
	}

	const setRole = (role: string) =>
		run(
			() =>
				unwrap(
					api.PATCH('/api/v1/users/{id}', {
						params: { path: { id: userId } },
						body: { role: role as Role }
					})
				),
			m.user_saved()
		);

	const setActive = (active: boolean) =>
		run(
			() =>
				unwrap(
					api.PATCH('/api/v1/users/{id}', { params: { path: { id: userId } }, body: { active } })
				),
			m.user_saved()
		);

	async function resetPassword(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		resetError = null;
		try {
			await unwrap(
				api.POST('/api/v1/users/{id}/password', {
					params: { path: { id: userId } },
					body: { password, revoke_tokens: revoke }
				})
			);
			toast.success(m.user_password_reset_done());
			password = '';
		} catch (error) {
			resetError = describeError(error);
		} finally {
			busy = false;
		}
	}

	async function confirmed() {
		if (confirm === 'totp') {
			await unwrap(api.DELETE('/api/v1/users/{id}/totp', { params: { path: { id: userId } } }));
			toast.success(m.user_totp_removed());
		} else if (confirm === 'oidc') {
			await unwrap(api.DELETE('/api/v1/users/{id}/oidc', { params: { path: { id: userId } } }));
			toast.success(m.user_oidc_removed());
		}
		onchanged();
		await load();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		size="lg"
		class="flex h-[min(53.75rem,calc(100dvh-2rem))] flex-col gap-0 overflow-hidden p-0"
	>
		<Dialog.Header class="shrink-0 px-4 pt-4 pr-12 pb-3">
			<Dialog.Title>{account ? userLabel(account) : m.loading()}</Dialog.Title>
		</Dialog.Header>
		{#if problem}
			<div class="px-4 pb-4"><LoadProblem {problem} onretry={() => load()} /></div>
		{:else if account}
			<div class="shrink-0 px-4 pb-3">
				<Segmented bind:value={part} options={parts} label={userLabel(account)} />
			</div>
			<div
				bind:this={scroller}
				class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overscroll-contain px-4 pb-4"
			>
				<div class={['flex flex-col gap-5', part !== 'account' && 'hidden']}>
					<Field.Field>
						<Field.Label for="user-role">{m.user_role()}</Field.Label>
						<Select
							id="user-role"
							value={account.role ?? 'user'}
							disabled={busy}
							options={[
								{ value: 'user', label: m.role_user() },
								{ value: 'admin', label: m.role_admin() }
							]}
							onchange={setRole}
						/>
					</Field.Field>
					<div class="flex items-center justify-between gap-3">
						<span>{account.active ? m.user_active() : m.user_inactive()}</span>
						<Button variant="outline" disabled={busy} onclick={() => setActive(!account!.active)}>
							{account.active ? m.user_deactivate() : m.user_activate()}
						</Button>
					</div>
					{#if !own}
						<form class="flex flex-col gap-3 border-t pt-4" onsubmit={resetPassword} novalidate>
							<Field.Field>
								<Field.Label for="user-password">{m.user_password_reset()}</Field.Label>
								<Input
									id="user-password"
									type="password"
									autocomplete="new-password"
									bind:value={password}
									aria-invalid={resetError ? true : undefined}
								/>
								{#if resetError}<Field.Error>{resetError}</Field.Error>{:else}
									<Field.Description>{m.password_rules()}</Field.Description>
								{/if}
							</Field.Field>
							<Choice bind:checked={revoke}>{m.user_revoke_tokens()}</Choice>
							<div>
								<Button type="submit" disabled={busy || password === ''}
									>{m.user_password_reset()}</Button
								>
							</div>
						</form>
					{/if}
					<div class="flex flex-col gap-2 border-t pt-4">
						<p class="text-sm text-muted-foreground">
							{account.totp_enabled ? m.user_totp_on() : m.user_totp_off()}
							·
							{account.linked_accounts.length > 0 ? m.user_oidc_on() : m.user_oidc_off()}
						</p>
						<div class="flex flex-wrap gap-2">
							{#if account.totp_enabled && !own}
								<Button variant="outline" disabled={busy} onclick={() => (confirm = 'totp')}>
									{m.user_totp_remove()}
								</Button>
							{/if}
							{#if account.linked_accounts.length > 0}
								<Button variant="outline" disabled={busy} onclick={() => (confirm = 'oidc')}>
									{m.user_oidc_remove()}
								</Button>
							{/if}
							{#if !own}
								<Button variant="destructive" disabled={busy} onclick={() => (deleting = true)}>
									{m.user_delete()}
								</Button>
							{/if}
						</div>
					</div>
				</div>
				{#if profileProblem}
					{#if part !== 'account'}
						<LoadProblem problem={profileProblem} onretry={loadProfileData} />
					{/if}
				{:else if profile}
					<div class={[part !== 'profile' && 'hidden']}>
						<ProfileForm data={profile} userId={account.id} part="person" onsaved={profileSaved} />
					</div>
					<div class={[part !== 'identifiers' && 'hidden']}>
						<ProfileForm data={profile} userId={account.id} part="numbers" onsaved={profileSaved} />
					</div>
				{:else if part !== 'account'}
					<Loading class="text-sm" />
				{/if}
			</div>
		{/if}
	</Dialog.Content>
</Dialog.Root>

<ConfirmDialog
	bind:open={() => confirm !== null, (value) => !value && (confirm = null)}
	title={confirm === 'totp' ? m.user_totp_remove() : m.user_oidc_remove()}
	description={confirm === 'totp' ? m.user_totp_remove_confirm() : m.user_oidc_remove_confirm()}
	confirmLabel={m.confirm_yes()}
	onconfirm={confirmed}
/>

{#if account}
	<UserDeleteDialog
		bind:open={deleting}
		{userId}
		username={userLabel(account)}
		ondeleted={() => {
			open = false;
			onchanged();
		}}
	/>
{/if}
