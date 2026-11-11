<script lang="ts">
	import SteadyText from '#lib/components/SteadyText.svelte';
	import type { Snippet } from 'svelte';
	import BookOpen from '@lucide/svelte/icons/book-open';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import Languages from '@lucide/svelte/icons/languages';
	import LogOut from '@lucide/svelte/icons/log-out';
	import Menu from '@lucide/svelte/icons/menu';
	import SearchIcon from '@lucide/svelte/icons/search';
	import SunMoon from '@lucide/svelte/icons/sun-moon';
	import Users from '@lucide/svelte/icons/users';
	import WifiOff from '@lucide/svelte/icons/wifi-off';
	import { mergeProps } from 'bits-ui';
	import { setMode, userPrefersMode } from 'mode-watcher';
	import { online } from 'svelte/reactivity/window';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { API_DOCS, BASE } from '#lib/base.ts';
	import Beam from '#lib/components/Beam.svelte';
	import HeaderSearch from '#lib/components/HeaderSearch.svelte';
	import Logo from '#lib/components/Logo.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import IconButton from '#lib/components/IconButton.svelte';
	import * as Tooltip from '#lib/components/ui/tooltip/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import * as Sheet from '#lib/components/ui/sheet/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { reportError } from '#lib/errors.ts';
	import { searchPlaces } from '#lib/header-search.ts';
	import { showPageSearch } from '#lib/page-search.ts';
	import { changeLanguage, getLocale, LANGUAGE_NAMES, locales, type Locale } from '#lib/i18n.ts';
	import { home, loginHref } from '#lib/navigation.ts';
	import { BADGE_TONES, badgeLabel, badgeText, badgeTone, inbox } from '#lib/inbox.svelte.ts';
	import { userLabel } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { THEME_OPTIONS } from '#lib/theme.ts';
	import { canListAllUsers } from '#lib/permissions.ts';
	import { phone } from '#lib/phone.svelte.ts';
	import { scope } from '#lib/scope.svelte.ts';
	import { href, isCurrent, SETTINGS, visibleSections, type Section } from '#lib/sections.ts';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import { onChange } from '#lib/watch.svelte.ts';
	import { Separator } from '#lib/components/ui/separator/index.ts';
	import LanguageChoices from '#lib/components/LanguageChoices.svelte';
	import ThemeChoices from '#lib/components/ThemeChoices.svelte';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';

	let { children }: { children: Snippet } = $props();

	// The menu in two groups with a line between them (Tobi, 26.10.2026): the work, then
	// administering and running Lekto, the system at the outer right (27.10.2026).
	const sections = $derived(visibleSections(session.isAdmin));
	const workSections = $derived(sections.filter((section) => section.group === 'work'));
	const setupSections = $derived(sections.filter((section) => section.group === 'setup'));
	const username = $derived(session.user ? userLabel(session.user) : '');
	const accountName = $derived(
		scope.allUsers ? m.account_menu_all_users({ username }) : m.account_menu({ username })
	);
	let menuOpen = $state(false);
	// A document opened from the inbox belongs to the inbox.
	const currentPath = $derived(
		page.url.searchParams.get('from') === 'inbox' ? `${home()}inbox` : page.url.pathname
	);

	async function signOut() {
		menuOpen = false;
		try {
			await session.logout();
		} catch (error) {
			reportError(error);
			return;
		}
		await goto(loginHref(home()), { replaceState: true });
	}

	const tone = $derived(badgeTone(inbox.summary));

	// The inbox counter covers what the scope setting covers.
	onChange(
		() => scope.allUsers,
		() => void inbox.refresh()
	);

	// Language and theme in the sheet on a phone, as pills in a row each.
	const languageOptions = locales.map((locale) => ({
		value: locale,
		label: LANGUAGE_NAMES[locale]
	}));
	const themeOptions = THEME_OPTIONS.map(({ value, label, icon }) => ({
		value,
		label: label(),
		icon
	}));

	async function open(section: Section) {
		menuOpen = false;
		await goto(href(section));
	}
</script>

{#snippet pill(section: Section, vertical: boolean)}
	{@const current = isCurrent(section, currentPath)}
	<a
		href={href(section)}
		aria-current={current ? 'page' : undefined}
		onclick={() => (menuOpen = false)}
		class={cn(
			'flex h-9 items-center gap-2 rounded-full px-3 text-sm whitespace-nowrap transition-colors hover:text-foreground 2xl:px-3.5',
			current ? 'bg-secondary font-medium text-foreground' : 'text-muted-foreground',
			vertical && 'h-11 rounded-xl px-4 text-base'
		)}
	>
		{#if vertical}<section.icon class="size-[18px]" aria-hidden="true" />{/if}
		<SteadyText text={section.label()} />
		{#if section.path === '/inbox' && inbox.summary && tone}
			<!-- Coloured by the worst lane in it; the label says what stands there. -->
			<span
				role="img"
				data-tone={tone}
				class={cn(
					'grid h-5 min-w-5 place-items-center rounded-full border px-1.5 text-xs font-semibold',
					BADGE_TONES[tone]
				)}
				aria-label={badgeLabel(inbox.summary)}
			>
				{badgeText(inbox.open)}
			</span>
		{/if}
	</a>
{/snippet}

{#snippet allUsersMark()}
	<!-- An admin who sees all users is told so at a glance. -->
	<span
		class="absolute -top-0.5 -right-0.5 grid size-4 place-items-center rounded-full border-2 border-card bg-lane-yellow text-lane-yellow-foreground"
		aria-hidden="true"
	>
		<Users class="size-2.5" />
	</span>
{/snippet}

<a
	href="#main"
	class="sr-only z-50 rounded-xl bg-primary px-4 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
	>{m.skip_to_content()}</a
>

<!-- A page that needs the room (the document view) marks itself `data-wide`: from the desktop
	width on it fills the window, and only its own areas scroll. One that only needs the width
	(the documents) marks itself `data-roomy`: as wide, and it scrolls as a page. -->
<div
	class="flex min-h-screen flex-col pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)] lg:has-[[data-wide]]:h-dvh"
>
	<header class="sticky top-0 z-40 border-b bg-card">
		<!-- Narrower gaps on a phone, and a little narrower below 380 pixels, so that the wordmark,
		     the magnifier and the menu fit beside each other down to 360. -->
		<div class="flex h-16 items-center gap-2 px-4 max-[380px]:px-3 sm:gap-4 sm:px-8 lg:gap-7">
			<a href={home()} class="relative rounded-md text-lg after:absolute after:-inset-y-1.5"
				><Logo /></a
			>
			<!-- Without a connection (web/DESIGN.md, "App"); the pages say what they cannot load. -->
			{#if online.current === false}
				<Badge variant="muted" size="md" role="status"
					><WifiOff aria-hidden="true" />{m.offline()}</Badge
				>
			{/if}

			<!-- The menu in the header from lg (web/DESIGN.md, "Navigation"): the work, then
			     administering and operating; below xl that second group behind "More" (German names
			     are long). -->
			<nav aria-label={m.nav_main()} class="hidden min-w-0 flex-1 items-center gap-1 lg:flex">
				{#each workSections as section (section.path)}
					{@render pill(section, false)}
				{/each}
				<Separator orientation="vertical" class="mx-2 h-5 self-center" />
				{#each setupSections as section (section.path)}
					<span class="hidden xl:contents">{@render pill(section, false)}</span>
				{/each}
				{#if setupSections.length > 0}
					{@const within = setupSections.some((section) => isCurrent(section, currentPath))}
					<DropdownMenu.Root>
						<DropdownMenu.Trigger
							class={cn(
								'flex h-9 items-center gap-1 rounded-full px-3 text-sm whitespace-nowrap transition-colors hover:text-foreground xl:hidden',
								within ? 'bg-secondary font-medium text-foreground' : 'text-muted-foreground'
							)}
						>
							<SteadyText text={m.nav_more()} />
							<ChevronDown class="size-4" aria-hidden="true" />
						</DropdownMenu.Trigger>
						<DropdownMenu.Content align="start" class="w-56">
							{#each setupSections as section (section.path)}
								<DropdownMenu.Item>
									{#snippet child({ props })}
										<a
											{...props}
											href={href(section)}
											aria-current={isCurrent(section, currentPath) ? 'page' : undefined}
										>
											<section.icon aria-hidden="true" />
											{section.label()}
										</a>
									{/snippet}
								</DropdownMenu.Item>
							{/each}
						</DropdownMenu.Content>
					</DropdownMenu.Root>
				{/if}
			</nav>

			<div class="ml-auto flex items-center gap-1.5 max-[380px]:gap-1 sm:gap-2">
				<!-- The field where there is room, else a magnifier to the documents page's own
				     field (`header-search.ts`); on that page it shows the field rather than opening
				     the page anew (`page-search.ts`). -->
				<HeaderSearch class={searchPlaces(session.isAdmin).field} />
				<IconButton
					href="{BASE}/documents#search"
					class={searchPlaces(session.isAdmin).icon}
					label={m.header_search_label()}
					side="bottom"
					onclick={(event: MouseEvent) => {
						if (showPageSearch()) event.preventDefault();
					}}
				>
					<SearchIcon aria-hidden="true" />
				</IconButton>
				<!-- On a phone the header holds only the magnifier and the menu: language, theme and
				     the account are in the sheet (Tobi, 26.10.2026). Wider, language and theme are in
				     the account's menu (web/DESIGN.md, "Navigation"). -->
				{#if !phone.current}
					<DropdownMenu.Root>
						<!-- The account as an avatar: round, its initial, its name as tooltip
						     (web/DESIGN.md, "Navigation"). -->
						<DropdownMenu.Trigger>
							{#snippet child({ props: menu })}
								<Tooltip.Root>
									<Tooltip.Trigger>
										{#snippet child({ props: tip })}
											<button
												{...mergeProps(menu, tip)}
												type="button"
												class="relative grid size-10 shrink-0 place-items-center rounded-full bg-primary text-md font-semibold text-primary-foreground uppercase outline-none select-none hover:bg-primary/80 focus-visible:ring-3 focus-visible:ring-ring/50"
												aria-label={accountName}
											>
												{username.slice(0, 1)}
												{#if scope.allUsers}{@render allUsersMark()}{/if}
											</button>
										{/snippet}
									</Tooltip.Trigger>
									<Tooltip.Content side="bottom">{accountName}</Tooltip.Content>
								</Tooltip.Root>
							{/snippet}
						</DropdownMenu.Trigger>
						<DropdownMenu.Content align="end" class="w-64">
							<DropdownMenu.Label class="flex flex-col gap-0.5">
								<span class="font-semibold">{username}</span>
								<span class="text-xs font-normal text-muted-foreground">
									{session.isAdmin ? m.role_admin() : m.role_user()}
								</span>
							</DropdownMenu.Label>
							<DropdownMenu.Separator />
							{#if canListAllUsers(session.user)}
								<DropdownMenu.CheckboxItem
									checked={scope.allUsers}
									onCheckedChange={(checked) => scope.set(checked)}
									class="items-start"
								>
									<Users aria-hidden="true" class="mt-0.5" />
									<span class="flex flex-col gap-0.5">
										{m.all_users()}
										<span class="text-xs text-muted-foreground">{m.all_users_hint()}</span>
									</span>
								</DropdownMenu.CheckboxItem>
								<DropdownMenu.Separator />
							{/if}
							<LanguageChoices />
							<DropdownMenu.Separator />
							<ThemeChoices />
							<DropdownMenu.Separator />
							<DropdownMenu.Item onSelect={() => goto(href(SETTINGS))}>
								<SETTINGS.icon aria-hidden="true" />
								{SETTINGS.label()}
							</DropdownMenu.Item>
							<!-- The API's own documentation (Swagger UI), in a new tab. -->
							<DropdownMenu.Item>
								{#snippet child({ props })}
									<a {...props} href={API_DOCS} target="_blank" rel="noopener noreferrer">
										<BookOpen aria-hidden="true" />
										{m.api_docs()}
										<span class="sr-only">({m.opens_in_new_tab()})</span>
										<ExternalLink aria-hidden="true" class="ml-auto text-muted-foreground" />
									</a>
								{/snippet}
							</DropdownMenu.Item>
							<DropdownMenu.Item onSelect={signOut}>
								<LogOut aria-hidden="true" />
								{m.sign_out()}
							</DropdownMenu.Item>
							<!-- The version that runs, small at the end (Tobi, 02.11.2026). -->
							{#if session.version}
								<DropdownMenu.Separator />
								<DropdownMenu.Label class="font-normal">
									{m.lekto_version({ version: session.version })}
								</DropdownMenu.Label>
							{/if}
						</DropdownMenu.Content>
					</DropdownMenu.Root>
				{/if}

				<!-- The menu below xl, at the outer right where the thumb is; the sheet opens from
				     the right. On a phone it holds the account too (Tobi, 26.10.2026, variant A). -->
				<Sheet.Root bind:open={menuOpen}>
					<Sheet.Trigger>
						{#snippet child({ props })}
							<IconButton
								{...props}
								class="relative lg:hidden"
								label={phone.current && scope.allUsers ? m.nav_open_all_users() : m.nav_open()}
								side="bottom"
							>
								<Menu aria-hidden="true" />
								{#if phone.current && scope.allUsers}{@render allUsersMark()}{/if}
							</IconButton>
						{/snippet}
					</Sheet.Trigger>
					<!-- `data-[side=right]:` to beat the sheet's own width of three quarters, which
					     left the theme's buttons no room on a phone (Tobi, 27.10.2026). -->
					<Sheet.Content
						side="right"
						class="gap-2 overflow-y-auto p-4 pt-[max(1rem,env(safe-area-inset-top))] pr-[max(1rem,env(safe-area-inset-right))] pb-[max(1rem,env(safe-area-inset-bottom))] data-[side=right]:w-80"
					>
						<Sheet.Header class="px-2">
							<Sheet.Title><Logo class="text-lg" /></Sheet.Title>
						</Sheet.Header>
						{#if phone.current}
							<div class="flex flex-col gap-0.5 px-4">
								<span class="text-base font-semibold">{username}</span>
								<span class="text-xs text-muted-foreground">
									{session.isAdmin ? m.role_admin() : m.role_user()}
								</span>
							</div>
							{#if canListAllUsers(session.user)}
								<label class="flex items-start gap-3 px-4 pt-3 pb-1">
									<span class="flex flex-1 flex-col gap-0.5">
										{m.all_users()}
										<span class="text-xs text-muted-foreground">{m.all_users_hint()}</span>
									</span>
									<Switch
										checked={scope.allUsers}
										onCheckedChange={(checked) => scope.set(checked)}
										class="mt-0.5"
									/>
								</label>
							{/if}
							<Separator class="mx-4 my-2 w-auto" />
						{/if}
						<nav aria-label={m.nav_main()} class="flex flex-col gap-1">
							{#each workSections as section (section.path)}
								{@render pill(section, true)}
							{/each}
							<Separator class="mx-4 my-2 w-auto" />
							{#each setupSections as section (section.path)}
								{@render pill(section, true)}
							{/each}
						</nav>
						{#if phone.current}
							<div class="mt-auto flex flex-col gap-1 pt-2">
								<Separator class="mx-4 my-2 w-auto" />
								<div class="flex h-10 items-center justify-between gap-2 px-4">
									<span
										id="sheet-language"
										class="flex items-center gap-2.5 text-sm text-muted-foreground"
									>
										<Languages class="size-4" aria-hidden="true" />
										{m.language_label()}
									</span>
									<Segmented
										size="sm"
										labelledby="sheet-language"
										options={languageOptions}
										value={getLocale()}
										onchange={(value) => changeLanguage(value as Locale)}
									/>
								</div>
								<div class="flex h-10 items-center justify-between gap-2 px-4">
									<span
										id="sheet-theme"
										class="flex items-center gap-2.5 text-sm text-muted-foreground"
									>
										<SunMoon class="size-4" aria-hidden="true" />
										{m.theme_label()}
									</span>
									<Segmented
										size="sm"
										names="hidden"
										labelledby="sheet-theme"
										options={themeOptions}
										value={userPrefersMode.current}
										onchange={(value) => setMode(value as 'light' | 'dark' | 'system')}
									/>
								</div>
								<Separator class="mx-4 my-2 w-auto" />
								<button
									type="button"
									onclick={() => open(SETTINGS)}
									class="flex h-10 items-center gap-2.5 rounded-xl px-4 text-md transition-colors hover:bg-muted"
								>
									<SETTINGS.icon class="size-4 text-muted-foreground" aria-hidden="true" />
									{SETTINGS.label()}
								</button>
								<a
									href={API_DOCS}
									target="_blank"
									rel="noopener noreferrer"
									class="flex h-10 items-center gap-2.5 rounded-xl px-4 text-md transition-colors hover:bg-muted"
								>
									<BookOpen class="size-4 text-muted-foreground" aria-hidden="true" />
									{m.api_docs()}
									<span class="sr-only">({m.opens_in_new_tab()})</span>
									<ExternalLink class="ml-auto size-4 text-muted-foreground" aria-hidden="true" />
								</a>
								<button
									type="button"
									onclick={signOut}
									class="flex h-10 items-center gap-2.5 rounded-xl px-4 text-md transition-colors hover:bg-muted"
								>
									<LogOut class="size-4 text-muted-foreground" aria-hidden="true" />
									{m.sign_out()}
								</button>
								{#if session.version}
									<Separator class="mx-4 my-2 w-auto" />
									<p class="px-4 text-xs text-muted-foreground">
										{m.lekto_version({ version: session.version })}
									</p>
								{/if}
							</div>
						{/if}
					</Sheet.Content>
				</Sheet.Root>
			</div>
		</div>
	</header>

	<main
		id="main"
		tabindex="-1"
		class="flex flex-1 justify-center px-4 py-8 outline-none sm:px-8 lg:has-[[data-wide]]:min-h-0 lg:has-[[data-wide]]:py-6"
	>
		<div
			class="w-full max-w-page has-[[data-roomy]]:max-w-wide has-[[data-wide]]:max-w-wide lg:has-[[data-wide]]:min-h-0"
		>
			{@render children()}
		</div>
	</main>
</div>
<Beam />
