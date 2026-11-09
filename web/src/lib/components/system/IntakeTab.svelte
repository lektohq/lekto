<script lang="ts">
	import { switchMailbox } from '#lib/rules/switch.ts';
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import OctagonX from '@lucide/svelte/icons/octagon-x';
	import Plus from '@lucide/svelte/icons/plus';
	import { onMount, untrack } from 'svelte';
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
	import MailboxLines from '#lib/components/system/MailboxLines.svelte';
	import { BASE } from '#lib/base.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError } from '#lib/errors.ts';
	import { events } from '#lib/events.svelte.ts';
	import { statusOf, type Mailbox, type StatusTone } from '#lib/mailboxes.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The tab "Eingangskanäle" of the page "System" (Tobi, 04.11.2026), for admins: the ways
	// documents come in besides the web UI and the API. So far mail: the mailboxes Lekto fetches
	// from, one row each (name and the state of its fetches, server, folders, interval, the last
	// fetch and why it failed), the switch that pauses it and the pencil that opens its dialog.
	// Its name opens its page (Tobi, 06.11.2026): what became of each mail it fetched. The end
	// of a fetch shows in the row at once (`mailbox.fetched`).
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

	onMount(load);

	// The end of a fetch shows in its row at once (Tobi, 06.11.2026), and after a break of the
	// stream the list loads anew.
	onMount(() => events.on('mailbox.fetched', () => void load()));
	$effect(() => {
		if (events.generation === 0) return;
		untrack(() => void load());
	});

	function create() {
		editing = null;
		open = true;
	}

	function edit(mailbox: Mailbox) {
		editing = mailbox;
		open = true;
	}

	async function switchOne(mailbox: Mailbox, enabled: boolean) {
		busy = mailbox.id;
		const changed = await switchMailbox(mailbox.id, enabled);
		if (changed)
			mailboxes = (mailboxes ?? []).map((item) => (item.id === changed.id ? changed : item));
		busy = null;
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
				<Card.Root as="li" size="row" class="relative flex flex-wrap items-center gap-3">
					<div class="flex min-w-0 flex-1 flex-col gap-1">
						<span class="flex flex-wrap items-center gap-2">
							<a
								href="{BASE}/system/mailboxes/{mailbox.id}"
								class="truncate font-medium after:absolute after:inset-0 hover:underline"
								aria-label={m.mailbox_open({ name: mailbox.name })}>{mailbox.name}</a
							>
							<StatusBadge tone={status.tone} label={status.label} icon={Icon} />
						</span>
						<MailboxLines {mailbox} />
					</div>
					<Switch
						bind:checked={() => mailbox.enabled, (enabled) => switchOne(mailbox, enabled)}
						disabled={busy === mailbox.id}
						class="relative z-10"
						aria-label={mailbox.enabled
							? m.mailbox_switch_off({ name: mailbox.name })
							: m.mailbox_switch_on({ name: mailbox.name })}
					/>
					<EditButton
						class="relative z-10"
						label={m.mailbox_edit_title({ name: mailbox.name })}
						onclick={() => edit(mailbox)}
					/>
				</Card.Root>
			{/each}
		</ul>
	{/if}
</section>

<MailboxDialog bind:open mailbox={editing} onsaved={load} />
