<script lang="ts">
	import Play from '@lucide/svelte/icons/play';
	import X from '@lucide/svelte/icons/x';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import InfoTip from '#lib/components/InfoTip.svelte';
	import PhoneSheet from '#lib/components/PhoneSheet.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Dialog from '#lib/components/ui/dialog/index.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { countOf, OPEN_STATES, type JobsSummary } from '#lib/jobs.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	// The maintenance (Tobi, 26.10.2026; a dialog of the tab "Jobs" for admins since 12.11.2026,
	// a sheet from the bottom on a phone): what Lekto does by itself for new documents, caught up
	// on over the existing ones, one row each: name, the why and how behind the info button, how
	// many jobs of its kind wait or run (from the tab's `summary`, which it asks every five
	// seconds), and a button that asks before it queues and then says how many were queued.
	interface Action {
		key: 'relate' | 'pages' | 'codes' | 'logos';
		name: string;
		info: string;
		confirm: string;
		/** The kind of the jobs it queues, counted from the summary. */
		kind: string;
		queue: () => Promise<number>;
		queued: (count: number) => string;
	}

	let {
		open = $bindable(false),
		summary,
		onqueued
	}: {
		open?: boolean;
		summary: JobsSummary;
		/** Something was queued: the tab asks for its counts again. */
		onqueued: () => void;
	} = $props();

	let logoFetch = $state<boolean | null>(null);
	let asked = $state<Action | null>(null);
	let confirming = $state(false);

	const documents = (count: number) =>
		count === 1
			? m.maintenance_queued_document_one()
			: m.maintenance_queued_documents({ count: formatNumber(count) });
	const contacts = (count: number) =>
		count === 1
			? m.maintenance_queued_contact_one()
			: m.maintenance_queued_contacts({ count: formatNumber(count) });

	const ACTIONS: Action[] = [
		{
			key: 'relate',
			name: m.maintenance_relate_name(),
			info: m.maintenance_relate_info(),
			confirm: m.maintenance_relate_confirm(),
			kind: 'pipeline.relate',
			queue: async () => (await unwrap(api.POST('/api/v1/pipeline/relate'))).queued,
			queued: documents
		},
		{
			key: 'pages',
			name: m.maintenance_pages_name(),
			info: m.maintenance_pages_info(),
			confirm: m.maintenance_pages_confirm(),
			kind: 'pipeline.catch_up',
			queue: async () => (await unwrap(api.POST('/api/v1/pipeline/render-pages'))).queued,
			queued: documents
		},
		{
			key: 'codes',
			name: m.maintenance_facts_name(),
			info: m.maintenance_facts_info(),
			confirm: m.maintenance_facts_confirm(),
			kind: 'pipeline.facts',
			queue: async () => (await unwrap(api.POST('/api/v1/pipeline/read-facts'))).queued,
			queued: documents
		},
		{
			key: 'logos',
			name: m.maintenance_logos_name(),
			info: m.maintenance_logos_info(),
			confirm: m.maintenance_logos_confirm(),
			kind: 'contacts.logo',
			queue: async () => (await unwrap(api.POST('/api/v1/contacts/logos/fetch'))).queued,
			queued: contacts
		}
	];

	async function loadPipeline() {
		try {
			logoFetch = (await unwrap(api.GET('/api/v1/pipeline'))).logo_fetch;
		} catch {
			// The row shows without the note; the button answers 503 if fetching is off.
		}
	}

	// Whether Lekto fetches logos, asked when the dialog first opens.
	$effect(() => {
		if (open && logoFetch === null) void loadPipeline();
	});

	function ask(action: Action) {
		asked = action;
		confirming = true;
	}

	async function run() {
		if (!asked) return;
		const count = await asked.queue();
		toast.success(count === 0 ? m.maintenance_queued_none() : asked.queued(count));
		onqueued();
	}

	function waiting(kind: string): number {
		const item = summary.kinds.find((entry) => entry.kind === kind);
		return item ? countOf(item, OPEN_STATES) : 0;
	}
</script>

{#snippet actions()}
	<ul>
		{#each ACTIONS as action (action.key)}
			{@const count = waiting(action.kind)}
			{@const off = action.key === 'logos' && logoFetch === false}
			<!-- On a phone the name has its line, the count and the button share the next. -->
			<li class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t py-3.5">
				<div class="flex min-w-0 flex-1 basis-56 items-center gap-1 max-sm:basis-full">
					<span class="font-medium">{action.name}</span>
					<InfoTip label={m.hint_about({ name: action.name })} size="sm" class="w-80">
						<p>{action.info}</p>
					</InfoTip>
				</div>
				<span class="text-meta text-muted-foreground tabular-nums max-sm:flex-1">
					{count > 0
						? m.maintenance_waiting({ count: formatNumber(count) })
						: m.maintenance_waiting_none()}
				</span>
				<div class="flex items-center gap-3">
					{#if off}
						<span class="text-meta text-muted-foreground">{m.maintenance_logos_off()}</span>
					{/if}
					<Button size="sm" variant="outline" disabled={off} onclick={() => ask(action)}>
						<Play aria-hidden="true" />{m.maintenance_run()}
					</Button>
				</div>
			</li>
		{/each}
	</ul>
{/snippet}

{#if phone.current}
	<PhoneSheet bind:open title={m.maintenance_title()} fit>
		{#snippet close()}
			<IconButton label={m.close()} onclick={() => (open = false)}>
				<X aria-hidden="true" />
			</IconButton>
		{/snippet}
		<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-4">
			<p class="pb-3 text-meta text-muted-foreground">{m.maintenance_info()}</p>
			{@render actions()}
		</div>
	</PhoneSheet>
{:else}
	<Dialog.Root bind:open>
		<Dialog.Content size="lg">
			<Dialog.Header>
				<Dialog.Title>{m.maintenance_title()}</Dialog.Title>
				<Dialog.Description>{m.maintenance_info()}</Dialog.Description>
			</Dialog.Header>
			{@render actions()}
		</Dialog.Content>
	</Dialog.Root>
{/if}

{#if asked}
	<ConfirmDialog
		bind:open={confirming}
		title={m.maintenance_confirm_title({ name: asked.name })}
		description={asked.confirm}
		confirmLabel={m.maintenance_run()}
		destructive={false}
		onconfirm={run}
	/>
{/if}
