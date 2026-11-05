<script lang="ts">
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import OctagonX from '@lucide/svelte/icons/octagon-x';
	import Plus from '@lucide/svelte/icons/plus';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import EditButton from '#lib/components/EditButton.svelte';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import InfoTip from '#lib/components/InfoTip.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import StatusBadge from '#lib/components/StatusBadge.svelte';
	import MailboxDialog from '#lib/components/system/MailboxDialog.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { cautions, statusOf, summaryOf, type Mailbox, type StatusTone } from '#lib/mailboxes.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { reasonText } from '#lib/reasons.ts';

	// The tab "Eingangskanäle" of the page "System" (Tobi, 04.11.2026), for admins: the ways
	// documents come in besides the web UI and the API. So far mail: the mailboxes Lekto fetches
	// from, one row each (name and the state of its fetches, server, folders, interval, the last
	// fetch and why it failed), the switch that pauses it and the pencil that opens its dialog.
	// `?mailbox=<id>` in the address opens that mailbox's dialog (the mail rules link here).
	let mailboxes = $state<Mailbox[] | null>(null);
	let problem = $state<string | null>(null);
	let busy = $state<string | null>(null);
	let open = $state(false);
	let editing = $state<Mailbox | null>(null);

	// A state with its icon; "not fetched yet" is a plain fact (web/DESIGN.md, "Badges").
	const ICONS: Partial<Record<StatusTone, typeof CircleCheck>> = {
		green: CircleCheck,
		red: OctagonX
	};

	async function load() {
		problem = null;
		try {
			mailboxes = await unwrap(api.GET('/api/v1/mailboxes'));
		} catch (error) {
			problem = describeError(error);
		}
	}

	onMount(async () => {
		await load();
		const wanted = page.url.searchParams.get('mailbox');
		const found = mailboxes?.find((item) => item.id === wanted);
		if (found) edit(found);
	});

	// The dialog closed: the address names no mailbox any more.
	$effect(() => {
		if (!open && page.url.searchParams.has('mailbox')) {
			void goto('?tab=intake', { replaceState: true, keepFocus: true });
		}
	});

	function create() {
		editing = null;
		open = true;
	}

	function edit(mailbox: Mailbox) {
		editing = mailbox;
		open = true;
	}

	async function switchMailbox(mailbox: Mailbox, enabled: boolean) {
		busy = mailbox.id;
		try {
			const changed = await unwrap(
				api.PATCH('/api/v1/mailboxes/{id}', {
					params: { path: { id: mailbox.id } },
					body: { enabled }
				})
			);
			mailboxes = (mailboxes ?? []).map((item) => (item.id === changed.id ? changed : item));
		} catch (error) {
			reportError(error);
		} finally {
			busy = null;
		}
	}
</script>

<section class="flex flex-col gap-3" aria-labelledby="intake-mail">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div class="flex items-center gap-1">
			<SectionTitle size="card" id="intake-mail">{m.intake_mail()}</SectionTitle>
			<InfoTip label={m.hint_about({ name: m.intake_mail() })} size="sm" class="w-80">
				<p>{m.intake_mail_info()}</p>
			</InfoTip>
		</div>
		<Button onclick={create}>
			<Plus aria-hidden="true" />
			{m.mailbox_new()}
		</Button>
	</div>

	{#if problem}
		<LoadProblem {problem} onretry={load} />
	{:else if !mailboxes}
		<Loading />
	{:else if mailboxes.length === 0}
		<EmptyNote>{m.mailbox_none()}</EmptyNote>
	{:else}
		<ul class="flex flex-col gap-2">
			{#each mailboxes as mailbox (mailbox.id)}
				{@const status = statusOf(mailbox)}
				{@const Icon = ICONS[status.tone]}
				<Card.Root as="li" size="row" class="flex flex-wrap items-center gap-3">
					<div class="flex min-w-0 flex-1 flex-col gap-1">
						<span class="flex flex-wrap items-center gap-2">
							<button
								type="button"
								class="truncate text-left font-medium hover:underline"
								onclick={() => edit(mailbox)}>{mailbox.name}</button
							>
							<StatusBadge tone={status.tone} label={status.label} icon={Icon} />
						</span>
						<span class="text-sm text-muted-foreground">{summaryOf(mailbox)}</span>
						{#if mailbox.status.error}
							<span class="text-sm text-destructive">{reasonText(mailbox.status.error)}</span>
						{/if}
						{#each cautions(mailbox) as caution (caution.key)}
							<span class="text-sm text-lane-yellow-foreground">{caution.text}</span>
						{/each}
					</div>
					<Switch
						bind:checked={() => mailbox.enabled, (enabled) => switchMailbox(mailbox, enabled)}
						disabled={busy === mailbox.id}
						aria-label={mailbox.enabled
							? m.mailbox_switch_off({ name: mailbox.name })
							: m.mailbox_switch_on({ name: mailbox.name })}
					/>
					<EditButton
						label={m.mailbox_edit_title({ name: mailbox.name })}
						onclick={() => edit(mailbox)}
					/>
				</Card.Root>
			{/each}
		</ul>
	{/if}
</section>

<MailboxDialog bind:open mailbox={editing} onsaved={load} />
