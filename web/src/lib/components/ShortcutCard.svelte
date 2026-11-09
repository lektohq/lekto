<script lang="ts">
	import { cardVariants } from '#lib/components/ui/card/index.ts';
	import { cn } from '#lib/utils.ts';
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { api } from '#lib/api/client.ts';
	import type { components } from '#lib/api/schema.ts';
	import { unwrap } from '#lib/api/call.ts';
	import IconButton from '#lib/components/IconButton.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { writeClipboard } from '#lib/clipboard.ts';
	import { reportError } from '#lib/errors.ts';
	import type { AppleDevice } from '#lib/install.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { lektoAddress, SHORTCUT_NAME } from '#lib/shortcut.ts';
	import { tokenChanges, tokensChanged } from '#lib/tokens.svelte.ts';

	// The shortcut "An Lekto senden" (web/DESIGN.md, "App"), on iPhone, iPad and Mac only: setting
	// it up creates a token that may only upload and shows it with Lekto's address, in the order
	// the Shortcuts app asks for them, and the link that adds the shortcut there.
	// `link`: the server's (`LEKTO_SHORTCUT_URL`); the card stands only where there is one.
	let { device, link }: { device: AppleDevice; link: string } = $props();

	type Token = components['schemas']['TokenOut'];

	let tokens = $state<Token[] | null>(null);
	let busy = $state(false);
	let token = $state<string | null>(null);
	let copied = $state<'token' | 'address' | null>(null);
	const address = lektoAddress(window.location.origin);
	const ready = $derived(tokens?.some((item) => item.scope === 'upload') ?? false);
	const ways = [
		{ title: m.shortcut_way_phone(), path: m.shortcut_share_path({ name: SHORTCUT_NAME }) },
		{ title: m.shortcut_way_mac(), path: m.shortcut_share_path({ name: SHORTCUT_NAME }) },
		{ title: m.shortcut_way_finder(), path: m.shortcut_finder_path({ name: SHORTCUT_NAME }) }
	];

	$effect(() => {
		void tokenChanges.version;
		api.GET('/api/v1/auth/tokens').then(
			(answer) => (tokens = answer.data ?? null),
			() => (tokens = null)
		);
	});

	async function setUp() {
		if (busy) return;
		busy = true;
		try {
			const created = await unwrap(
				api.POST('/api/v1/auth/tokens', {
					body: { name: m.shortcut_token_name({ device }), scope: 'upload', expires_at: null }
				})
			);
			token = created.token;
			copied = null;
			tokensChanged();
		} catch (error) {
			reportError(error);
		} finally {
			busy = false;
		}
	}

	async function copy(what: 'token' | 'address') {
		const text = what === 'token' ? token : address;
		if (text && (await writeClipboard(text))) copied = what;
	}
</script>

<!-- The action under the text, not beside the title: its words are long ("Weiteres Gerät
     einrichten") and would squeeze the title on a phone. -->
<Card.Root>
	<Card.Header>
		<Card.Title class="flex flex-wrap items-center gap-2">
			{m.shortcut_title()}
			{#if ready}
				<Badge variant="green"><Check aria-hidden="true" />{m.shortcut_ready()}</Badge>
			{/if}
		</Card.Title>
		<Card.Description>{m.shortcut_text()}</Card.Description>
	</Card.Header>
	<Card.Content class="flex flex-col gap-4">
		{#if ready}
			<ul class="grid gap-2 text-sm sm:grid-cols-3">
				{#each ways as way (way.title)}
					<li class={cn(cardVariants({ size: 'sm' }), 'text-muted-foreground')}>
						<span class="block font-medium text-foreground">{way.title}</span>
						{way.path}
					</li>
				{/each}
			</ul>
		{/if}
		<Button
			variant={ready ? 'outline' : 'default'}
			class="self-start"
			aria-disabled={busy}
			onclick={setUp}
		>
			{ready ? m.shortcut_another() : m.shortcut_set_up()}
		</Button>
	</Card.Content>
</Card.Root>

<Dialog.Root bind:open={() => token !== null, (open) => !open && (token = null)}>
	<Dialog.Content size="md">
		<Dialog.Header>
			<Dialog.Title>{m.shortcut_dialog_title()}</Dialog.Title>
			<Dialog.Description>{m.shortcut_dialog_text({ name: SHORTCUT_NAME })}</Dialog.Description>
		</Dialog.Header>
		{#if token}
			{@render field('token', m.shortcut_token_label(), token, m.token_created_hint())}
			{@render field('address', m.shortcut_address_label(), address)}
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (token = null)}>{m.secret_done()}</Button>
				<Button href={link} target="_blank" rel="noopener">{m.shortcut_add()}</Button>
			</Dialog.Footer>
		{/if}
	</Dialog.Content>
</Dialog.Root>

{#snippet field(what: 'token' | 'address', label: string, value: string, hint?: string)}
	<div class="flex flex-col gap-1.5">
		<p class="text-sm font-medium">{label}</p>
		<div class="flex items-center gap-1 rounded-xl border bg-secondary py-1 pr-1 pl-3">
			<span class="min-w-0 flex-1 font-mono text-sm break-all select-all">{value}</span>
			<IconButton label={m.shortcut_copy({ what: label })} onclick={() => void copy(what)}>
				{#if copied === what}<Check aria-hidden="true" />{:else}<Copy aria-hidden="true" />{/if}
			</IconButton>
		</div>
		{#if hint}<p class="text-sm text-muted-foreground">{hint}</p>{/if}
	</div>
{/snippet}
