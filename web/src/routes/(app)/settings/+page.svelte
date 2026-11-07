<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import { BASE } from '#lib/base.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import PasswordCard from '#lib/components/PasswordCard.svelte';
	import InfoHint from '#lib/components/InfoHint.svelte';
	import ProfileForm from '#lib/components/ProfileForm.svelte';
	import TabBar from '#lib/components/TabBar.svelte';
	import NotificationsCard from '#lib/components/NotificationsCard.svelte';
	import ShortcutCard from '#lib/components/ShortcutCard.svelte';
	import TokensCard from '#lib/components/TokensCard.svelte';
	import { appleDevice } from '#lib/install.svelte.ts';
	import TotpCard from '#lib/components/TotpCard.svelte';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { httpUrl } from '#lib/http-url.ts';
	import { userLabel } from '#lib/masterdata.svelte.ts';
	import { oidcErrorMessage } from '#lib/oidc-errors.ts';
	import { m } from '#lib/paraglide/messages.js';
	import {
		loadProfile,
		type Profile,
		type ProfileData,
		SETTINGS_TABS,
		type SettingsTab,
		settingsTab
	} from '#lib/profile.ts';
	import { session } from '#lib/session.svelte.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';

	// The settings (Tobi, 02.11.2026): the account, then tabs for the profile, the sign-in, the
	// API tokens and, last, the identifiers at contacts; the tab stands in the URL.
	type Me = components['schemas']['Me'];
	type Oidc = components['schemas']['OidcInfo'];

	const tab = $derived(settingsTab(page.url.searchParams));
	// The shortcut for the share sheet exists for Apple's devices only.
	const device = appleDevice();
	const LABELS: Record<SettingsTab, () => string> = {
		profile: m.profile_title,
		'sign-in': m.settings_tab_sign_in,
		notifications: m.notifications_tab,
		tokens: m.token_title,
		identifiers: m.profile_numbers
	};
	let me = $state<Me | null>(null);
	let oidc = $state<Oidc | null>(null);
	let profile = $state<ProfileData | null>(null);
	let problem = $state<string | null>(null);
	let unlinking = $state(false);
	const linkError = $derived(oidcErrorMessage(new URLSearchParams(page.url.search).get('error')));

	async function load() {
		try {
			[me, oidc, profile] = await Promise.all([
				unwrap(api.GET('/api/v1/auth/me')),
				unwrap(api.GET('/api/v1/auth/oidc')),
				loadProfile(null)
			]);
		} catch (error) {
			problem = describeError(error);
		}
	}

	onMount(load);

	// A new display name shows at once in the account card and menu too.
	async function saved(changed: Profile) {
		if (profile) profile.profile = changed;
		try {
			[me] = await Promise.all([unwrap(api.GET('/api/v1/auth/me')), session.load()]);
		} catch (error) {
			reportError(error);
		}
	}

	async function link() {
		try {
			const { authorization_url } = await unwrap(
				api.POST('/api/v1/auth/oidc/link', {
					params: { query: { next: `${BASE}/settings?tab=sign-in` } }
				})
			);
			// Only a web address: the browser is never sent to another scheme from an answer.
			const target = httpUrl(authorization_url, location.origin);
			if (!target) {
				toast.error(m.oidc_link_bad_url());
				return;
			}
			window.location.assign(target);
		} catch (error) {
			reportError(error);
		}
	}

	async function unlink() {
		await unwrap(api.DELETE('/api/v1/auth/oidc/link'));
		toast.success(m.oidc_unlinked());
		await load();
	}

	async function endOthers() {
		const { ended } = await unwrap(api.DELETE('/api/v1/auth/sessions'));
		toast.success(m.sessions_ended({ count: ended }));
	}
	let ending = $state(false);
</script>

<svelte:head><title>{LABELS[tab]()} · {m.nav_settings()} · {m.app_name()}</title></svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader title={m.nav_settings()} />

	{#if linkError}
		<Alert.Root variant="caution"><Alert.Description>{linkError}</Alert.Description></Alert.Root>
	{/if}

	{#if problem}
		<LoadProblem {problem} onretry={load} />
	{:else if me === null || profile === null}
		<Loading />
	{:else}
		<Card.Root>
			<Card.Header>
				<Card.Title>{userLabel(me.user)}</Card.Title>
				<Card.Description>
					{me.user.username} · {me.user.role === 'admin' ? m.role_admin() : m.role_user()}
				</Card.Description>
			</Card.Header>
		</Card.Root>

		<TabBar
			label={m.settings_tabs()}
			tabs={SETTINGS_TABS.map((value) => ({
				key: value,
				href: `?tab=${value}`,
				label: LABELS[value](),
				count: value === 'identifiers' ? profile?.profile.numbers.length : undefined
			}))}
			current={tab}
		/>

		{#key tab}
			{#if tab === 'profile'}
				<Card.Root>
					<Card.Header>
						<Card.Title class="flex items-center gap-1">
							{m.profile_title()}
							<InfoHint text={m.profile_own_hint()} about={m.profile_title()} />
						</Card.Title>
					</Card.Header>
					<Card.Content>
						<ProfileForm data={profile} part="person" onsaved={saved} />
					</Card.Content>
				</Card.Root>
			{:else if tab === 'sign-in'}
				{#if me.has_password}<PasswordCard />{/if}
				<TotpCard enabled={me.totp_enabled} onchanged={load} />

				{#if oidc?.enabled || me.linked_accounts.length > 0}
					<Card.Root>
						<Card.Header>
							<Card.Title>{oidc?.display_name ?? m.oidc_title()}</Card.Title>
							<Card.Description>
								{me.linked_accounts.length > 0 ? m.oidc_linked() : m.oidc_not_linked()}
							</Card.Description>
						</Card.Header>
						<Card.Content class="flex flex-wrap gap-2">
							{#if oidc?.enabled}
								<Button variant="outline" onclick={link}>{m.oidc_link()}</Button>
							{/if}
							{#if me.linked_accounts.length > 0}
								{#if me.has_password}
									<Button variant="outline" onclick={() => (unlinking = true)}>
										{m.oidc_unlink()}
									</Button>
								{:else}
									<p class="text-sm text-muted-foreground">{m.oidc_unlink_needs_password()}</p>
								{/if}
							{/if}
						</Card.Content>
					</Card.Root>
				{/if}

				<Card.Root>
					<Card.Header>
						<Card.Title>{m.sessions_title()}</Card.Title>
						<Card.Description>{m.sessions_hint()}</Card.Description>
					</Card.Header>
					<Card.Content>
						<Button variant="outline" onclick={() => (ending = true)}
							>{m.sessions_end_others()}</Button
						>
					</Card.Content>
				</Card.Root>
			{:else if tab === 'notifications'}
				<NotificationsCard />
			{:else if tab === 'tokens'}
				<!-- On iPhone, iPad and Mac the shortcut first (web/DESIGN.md, "Settings"). -->
				{#if device}<ShortcutCard {device} />{/if}
				<TokensCard />
			{:else}
				<ProfileForm data={profile} part="numbers" onsaved={saved} />
			{/if}
		{/key}
	{/if}
</div>

<ConfirmDialog
	bind:open={unlinking}
	title={m.oidc_unlink()}
	description={m.oidc_unlink_confirm()}
	confirmLabel={m.oidc_unlink()}
	onconfirm={unlink}
/>
<ConfirmDialog
	bind:open={ending}
	title={m.sessions_end_others()}
	description={m.sessions_end_confirm()}
	confirmLabel={m.sessions_end_others()}
	destructive={false}
	onconfirm={endOthers}
/>
