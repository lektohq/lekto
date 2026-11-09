<script lang="ts">
	import CircleCheck from '@lucide/svelte/icons/circle-check';
	import OctagonX from '@lucide/svelte/icons/octagon-x';
	import Pencil from '@lucide/svelte/icons/pencil';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import { untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import { openBeam } from '#lib/beam.svelte.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import InfoTip from '#lib/components/InfoTip.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import Select from '#lib/components/Select.svelte';
	import StatusBadge from '#lib/components/StatusBadge.svelte';
	import MailboxDialog from '#lib/components/system/MailboxDialog.svelte';
	import MailboxLines from '#lib/components/system/MailboxLines.svelte';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as Table from '#lib/components/ui/table/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { events } from '#lib/events.svelte.ts';
	import { formatMoment, formatNumber } from '#lib/i18n.ts';
	import {
		failedSteps,
		noteOf,
		stepsDone,
		takenText,
		VIEW_LABELS,
		VIEW_OUTCOMES,
		VIEW_TONE,
		viewCount,
		viewOf,
		VIEWS,
		waitingText,
		type MailItem,
		type MailSummary,
		type MailView
	} from '#lib/mail-log.ts';
	import { folderLabel, statusOf, type Mailbox, type StatusTone } from '#lib/mailboxes.ts';
	import { rememberedPageSize } from '#lib/page-size.ts';
	import { SummaryPager } from '#lib/summary-pager.svelte.ts';
	import LogCard from '#lib/components/LogCard.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The page of a mailbox (Tobi, 06.11.2026; mock „Postfach-Seite mit Verarbeitung“), built as
	// the page of a webhook: its head with the state of its fetches, "Bearbeiten" (the dialog),
	// "Jetzt abrufen" and delete; a note when mails without a rule now match a rule (they come at
	// the next fetch); then its log, a table with pages: what became of each mail it fetched, by
	// outcome and by rule, with the documents it made and the steps on the server. The end of
	// each fetch of it shows at once (`mailbox.fetched`).
	const id = $derived(page.params.id ?? '');
	let mailbox = $state<Mailbox | null>(null);
	let problem = $state<string | null>(null);
	let editing = $state(false);
	let removing = $state(false);
	let fetching = $state(false);
	let view = $state<MailView>('all');
	let rule = $state('');

	// A state with its icon; "not fetched yet" is a plain fact (web/DESIGN.md, "Badges").
	const ICONS: Partial<Record<StatusTone, typeof CircleCheck>> = {
		green: CircleCheck,
		red: OctagonX
	};
	const status = $derived(mailbox ? statusOf(mailbox) : null);

	const log = new SummaryPager<MailItem, MailSummary>(async (offset, limit) => {
		const path = { id };
		const rule_id = rule || undefined;
		const [found, summary] = await Promise.all([
			unwrap(
				api.GET('/api/v1/mailboxes/{id}/mails', {
					params: { path, query: { outcome: VIEW_OUTCOMES[view], rule_id, offset, limit } }
				})
			),
			unwrap(
				api.GET('/api/v1/mailboxes/{id}/mails/summary', { params: { path, query: { rule_id } } })
			)
		]);
		return { items: found.items, total: found.total, summary };
	}, rememberedPageSize('mails'));
	const mails = log.pager;
	const summary = $derived(log.summary);

	const views = $derived(
		VIEWS.map((value) => ({
			value,
			label: VIEW_LABELS[value](),
			count: summary ? formatNumber(viewCount(summary, value)) : undefined
		}))
	);
	const ruleOptions = $derived([
		{ value: '', label: m.mailbox_rules_all() },
		...(summary?.rules ?? []).map((item) => ({ value: item.id, label: item.name }))
	]);
	const waiting = $derived(summary ? waitingText(summary) : '');
	const filtered = $derived(view !== 'all' || rule !== '');
	const NUMBER = 'text-right tabular-nums';

	/** Load the mailbox; whether it is there. */
	async function load(wanted: string): Promise<boolean> {
		problem = null;
		try {
			const found = await unwrap(
				api.GET('/api/v1/mailboxes/{id}', { params: { path: { id: wanted } } })
			);
			if (wanted === id) mailbox = found;
			return wanted === id;
		} catch (error) {
			if (wanted === id) problem = describeError(error);
			return false;
		}
	}

	$effect(() => {
		const wanted = id;
		mailbox = null;
		// Only the mailbox starts the page over, not the choice it reads while it loads. Its log
		// follows the mailbox: one that is not there has one problem on the page, not two.
		untrack(() => {
			view = 'all';
			rule = '';
			log.summary = null;
		});
		void load(wanted).then((found) => {
			if (found) untrack(() => void log.reset());
		});
	});

	// Live (Tobi, 06.11.2026): the end of a fetch of this mailbox shows what became of its mails
	// at once; after a break of the stream the page loads anew, an end may have been missed.
	$effect(() => {
		const wanted = id;
		return events.on('mailbox.fetched', (event) => {
			if (event.mailbox_id !== wanted) return;
			void load(wanted).then((found) => {
				if (found) void mails.refresh();
			});
		});
	});

	$effect(() => {
		if (events.generation === 0) return;
		untrack(() => {
			void load(id).then((found) => {
				if (found) void mails.refresh();
			});
		});
	});

	function show(next: string) {
		view = next as MailView;
		void mails.go(1);
	}

	function chooseRule(next: string) {
		rule = next;
		void mails.go(1);
	}

	async function fetchNow() {
		fetching = true;
		try {
			await unwrap(api.POST('/api/v1/mailboxes/{id}/fetch', { params: { path: { id } } }));
			toast.success(m.mailbox_fetch_queued());
		} catch (error) {
			reportError(error);
		} finally {
			fetching = false;
		}
	}

	async function saved() {
		if (await load(id)) await mails.reload();
	}

	async function remove() {
		await unwrap(api.DELETE('/api/v1/mailboxes/{id}', { params: { path: { id } } }));
		toast.success(m.mailbox_deleted());
		await goto(`${BASE}/system?tab=intake`);
	}

	function documents(item: MailItem) {
		const ids = item.documents.map((document) => document.id);
		openBeam(ids, ids[0], item.subject || m.mail_rule_no_subject());
	}
</script>

<svelte:head>
	<title>{mailbox?.name ?? m.mailbox_short()} · {m.app_name()}</title>
</svelte:head>

<div class="flex flex-col gap-6">
	<PageHeader
		title={mailbox?.name ?? m.mailbox_short()}
		back={{ href: `${BASE}/system?tab=intake`, label: m.system_tab_intake() }}
	>
		{#snippet actions()}
			{#if mailbox}
				<Button variant="outline" onclick={() => (editing = true)}>
					<Pencil aria-hidden="true" />
					{m.edit_do()}
				</Button>
				{#if mailbox.enabled}
					<Button variant="outline" disabled={fetching} onclick={fetchNow}>
						<RefreshCw aria-hidden="true" />
						{m.mailbox_fetch()}
					</Button>
				{/if}
				<IconButton
					label={m.mailbox_delete_title({ name: mailbox.name })}
					onclick={() => (removing = true)}
				>
					<Trash2 aria-hidden="true" />
				</IconButton>
			{/if}
		{/snippet}
		{#snippet below()}
			{#if mailbox && status}
				<span class="mt-1 flex flex-wrap items-center gap-2">
					<StatusBadge tone={status.tone} label={status.label} icon={ICONS[status.tone]} />
					{#if !mailbox.enabled}<Badge variant="muted">{m.mailbox_paused()}</Badge>{/if}
				</span>
				<MailboxLines {mailbox} />
			{/if}
		{/snippet}
	</PageHeader>

	{#if problem}
		<LoadProblem {problem} onretry={() => void load(id)} />
	{:else if !mailbox}
		<Loading />
	{/if}

	{#if waiting}
		<Alert.Root variant="note" class="flex flex-wrap items-center justify-between gap-3">
			<Alert.Description>{waiting}</Alert.Description>
			{#if mailbox?.enabled}
				<Button size="sm" disabled={fetching} onclick={fetchNow}>
					<RefreshCw aria-hidden="true" />
					{m.mailbox_fetch()}
				</Button>
			{/if}
		</Alert.Root>
	{/if}

	{#if mailbox && summary}
		<div class="flex flex-wrap items-center justify-between gap-3">
			<Segmented label={m.mailbox_log()} value={view} onchange={show} options={views} />
			{#if summary.rules.length > 0}
				<Select
					aria-label={m.mailbox_rule_filter()}
					class="w-auto min-w-56"
					value={rule}
					onchange={chooseRule}
					options={ruleOptions}
				/>
			{/if}
		</div>
	{/if}

	{#if mailbox}
		<LogCard
			id="mailbox-log"
			title={m.mailbox_log()}
			pager={mails}
			{filtered}
			none={m.mailbox_mails_none()}
			noneChosen={m.mailbox_mails_none_chosen()}
			table="mails"
			tableClass="min-w-[900px] text-meta"
		>
			{#snippet tip()}
				<!-- The tip names how many the log keeps, which the summary brings: shown with it. -->
				{#if summary}
					<InfoTip label={m.hint_about({ name: m.mailbox_log() })} size="sm" class="w-80">
						<p>{m.mailbox_log_info({ kept: formatNumber(summary.kept) })}</p>
					</InfoTip>
				{/if}
			{/snippet}
			{#snippet head()}
				<Table.Head class="pl-0">{m.mailbox_col_fetched()}</Table.Head>
				<Table.Head>{m.mailbox_col_mail()}</Table.Head>
				<Table.Head>{m.mailbox_col_folder()}</Table.Head>
				<Table.Head>{m.mailbox_col_result()}</Table.Head>
				<Table.Head class={NUMBER}>{m.mailbox_col_documents()}</Table.Head>
				<Table.Head class="pr-0">{m.mailbox_col_server()}</Table.Head>
			{/snippet}
			{#snippet row(item)}
				{@const shown = viewOf(item.outcome)}
				{@const taken = takenText(item)}
				{@const note = noteOf(item)}
				<Table.Row class="align-top">
					<Table.Cell class="pl-0 text-muted-foreground tabular-nums">
						{formatMoment(item.fetched_at, 'short')}
					</Table.Cell>
					<Table.Cell class="max-w-[18rem] whitespace-normal">
						{#if item.forgotten}
							<span class="text-muted-foreground">{m.mailbox_forgotten()}</span>
						{:else}
							<span class="block truncate font-medium">
								{item.subject || m.mail_rule_no_subject()}
							</span>
							<span class="block truncate text-xs text-muted-foreground">{item.sender}</span>
						{/if}
					</Table.Cell>
					<Table.Cell>{folderLabel(item.folder)}</Table.Cell>
					<Table.Cell class="whitespace-normal">
						{#if shown !== 'all'}
							<Badge variant={VIEW_TONE[shown]}>{VIEW_LABELS[shown]()}</Badge>
						{/if}
						{#if taken}
							<span class="block text-xs text-muted-foreground">{taken}</span>
						{/if}
						{#if note}
							<span
								class={cn(
									'block text-xs',
									item.next_rule ? 'text-lane-yellow-foreground' : 'text-muted-foreground'
								)}
							>
								{note}
							</span>
						{/if}
					</Table.Cell>
					<Table.Cell class={NUMBER}>
						{#if item.documents.length}
							<button
								type="button"
								class={cn(buttonVariants({ variant: 'link', size: 'inline' }))}
								aria-label={m.mailbox_documents_open({
									subject: item.subject || m.mail_rule_no_subject()
								})}
								onclick={() => documents(item)}
							>
								{formatNumber(item.documents.length)}
							</button>
						{:else}
							<span class="text-muted-foreground">–</span>
						{/if}
						{#if item.documents_hidden}
							<span class="block text-xs text-muted-foreground">
								{m.mailbox_hidden_documents({ count: item.documents_hidden })}
							</span>
						{/if}
					</Table.Cell>
					<Table.Cell class="pr-0 whitespace-normal">
						{#if item.steps.length}
							{stepsDone(item)}
							{#each failedSteps(item) as failed (failed)}
								<span class="block text-xs text-lane-yellow-foreground">{failed}</span>
							{/each}
						{:else}
							<span class="text-muted-foreground">–</span>
						{/if}
					</Table.Cell>
				</Table.Row>
			{/snippet}
		</LogCard>
	{/if}
</div>

<MailboxDialog bind:open={editing} {mailbox} onsaved={saved} />
<ConfirmDialog
	bind:open={removing}
	title={m.mailbox_delete_title({ name: mailbox?.name ?? '' })}
	description={m.mailbox_delete_description()}
	confirmLabel={m.delete_title()}
	onconfirm={remove}
/>
