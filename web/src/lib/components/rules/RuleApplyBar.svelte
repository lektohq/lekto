<script lang="ts">
	import LoaderCircle from '@lucide/svelte/icons/loader-circle';
	import { BASE } from '#lib/base.ts';
	import { bulkDocuments } from '#lib/bulk.ts';
	import SelectionBar from '#lib/components/SelectionBar.svelte';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.ts';
	import { ChoiceBox } from '#lib/components/ui/choice/index.ts';
	import { Progress } from '#lib/components/ui/progress/index.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { aheadText, applicationResult, type Application } from '#lib/rules/apply.ts';
	import { cn } from '#lib/utils.ts';

	// The bar of a rule's dry run (web/DESIGN.md, "Choosing many"). While choosing: a box that
	// chooses every document without a conflict, how many are chosen, how far the dry run has
	// loaded ("Anhalten" while it loads, "Weiter laden" once stopped), and "Anwenden", with
	// "Aktivieren und anwenden" while the rule is paused. Once applied, how far the application
	// has come in place of all that: waiting for the worker (what comes before it, or that no
	// worker takes jobs), running, done or stopped.
	let {
		chosen,
		allChosen,
		loaded,
		conflicts,
		loading,
		complete,
		offerSwitchOn,
		busy,
		application,
		waiting,
		rule,
		onchoose,
		onstop,
		onmore,
		onapply,
		ondetails
	}: {
		/** Documents chosen, conflicts accepted included. */
		chosen: number;
		/** Every loaded document without a conflict is chosen. */
		allChosen: boolean;
		/** Documents the dry run has loaded. */
		loaded: number;
		/** Of them, those with a conflict. */
		conflicts: number;
		/** The dry run loads its next pages. */
		loading: boolean;
		/** The dry run has every document. */
		complete: boolean;
		/** The rule is paused and the reader may switch it on. */
		offerSwitchOn: boolean;
		/** Applying is being started. */
		busy: boolean;
		application: Application | null;
		/** What a queued application waits for (`GET /jobs/summary`), once known. */
		waiting: { jobs: number; still: boolean } | null;
		/** The rule's id, for the way back to it. */
		rule: string;
		onchoose: (all: boolean) => void;
		onstop: () => void;
		onmore: () => void;
		onapply: (switchOn: boolean) => void;
		ondetails: (application: Application) => void;
	} = $props();

	const finished = $derived(application?.status === 'done' || application?.status === 'failed');
	const count = $derived.by(() => {
		switch (application?.status) {
			case undefined:
				return m.selection_selected({ count: formatNumber(chosen) });
			case 'queued':
				return waiting?.still ? m.jobs_worker_stale() : m.rule_apply_waiting();
			case 'running':
				return m.rule_apply_running();
			case 'done':
				return m.rule_apply_done();
			case 'failed':
				return m.rule_apply_failed();
		}
	});
	const stopped = $derived(!loading && !complete);
	// On a desktop the bar has room for an icon button before the count; a box or a mark stands
	// where its text would start.
	const inset = $derived(phone.current ? undefined : 'ml-2.5');
	const progress = $derived(
		application
			? m.bulk_running({
					done: formatNumber(application.done),
					total: formatNumber(application.total)
				})
			: ''
	);
</script>

{#snippet lead()}
	{#if !application}
		<ChoiceBox
			class={inset}
			checked={allChosen}
			aria-label={m.rule_preview_select_all()}
			onchange={(event) => onchoose(event.currentTarget.checked)}
		/>
	{:else if application.status === 'queued' && waiting?.still}
		<!-- As the page "System" says it (web/DESIGN.md, "Colour roles": lane colours mean state). -->
		<span
			aria-hidden="true"
			class={cn(
				'size-2.5 shrink-0 rounded-full bg-lane-yellow-foreground ring-4 ring-lane-yellow',
				inset
			)}
		></span>
	{:else if application.status === 'queued'}
		<LoaderCircle
			class={cn('size-4 shrink-0 text-muted-foreground motion-safe:animate-spin', inset)}
			aria-hidden="true"
		/>
	{/if}
{/snippet}

{#snippet hint()}
	{#if !application}
		{#if loading}
			{m.rule_preview_loading({ documents: bulkDocuments(loaded) })}
		{:else if stopped}
			{m.rule_preview_stopped({ documents: bulkDocuments(loaded) })}
		{:else}
			{m.rule_preview_total({ documents: bulkDocuments(loaded) })}{#if conflicts > 0}
				· {m.rule_preview_conflicts({ count: formatNumber(conflicts) })}{/if}
		{/if}
	{:else if application.status === 'queued'}
		<span aria-live="polite">
			{#if waiting}{waiting.still ? m.rule_apply_no_worker() : aheadText(waiting.jobs)}{/if}
			{m.rule_apply_leave()}
		</span>
	{:else if application.status === 'running'}
		<span class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
			<Progress
				value={application.done}
				max={Math.max(application.total, 1)}
				class="max-w-48"
				aria-label={progress}
			/>
			<span class="tabular-nums" aria-live="polite">{progress}</span>
			<span>{m.rule_apply_leave()}</span>
		</span>
	{:else if application.status === 'failed'}
		<span class="text-destructive" role="alert">
			{application.error ?? ''}
			{applicationResult(application)}
		</span>
	{:else}
		<span aria-live="polite">{applicationResult(application)}</span>
	{/if}
{/snippet}

{#snippet trail()}
	{#if !application && loading}
		<Button variant="ghost" size="sm" onclick={onstop}>{m.rule_preview_stop()}</Button>
	{:else if !application && stopped}
		<Button variant="ghost" size="sm" onclick={onmore}>{m.rule_preview_more()}</Button>
	{/if}
{/snippet}

{#snippet actions()}
	{#if !application}
		<Button
			variant={offerSwitchOn ? 'outline' : 'default'}
			size="sm"
			disabled={busy || loading || chosen === 0}
			onclick={() => onapply(false)}
		>
			{m.rule_apply_action()}
		</Button>
		{#if offerSwitchOn}
			<Button size="sm" disabled={busy || loading || chosen === 0} onclick={() => onapply(true)}>
				{m.rule_switch_on_apply()}
			</Button>
		{/if}
	{:else if application.status === 'queued'}
		<a href="{BASE}/system?tab=jobs" class={cn(buttonVariants({ variant: 'ghost', size: 'sm' }))}>
			{m.rule_apply_jobs()}
		</a>
	{:else if finished}
		{#if application.skipped.length > 0}
			<Button variant="ghost" size="sm" onclick={() => ondetails(application)}>
				{m.bulk_details()}
			</Button>
		{/if}
		<a href="{BASE}/rules/{rule}" class={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
			{m.rule_apply_back()}
		</a>
	{/if}
{/snippet}

<SelectionBar
	{count}
	busy={busy || application?.status === 'running'}
	lead={!application || application.status === 'queued' ? lead : undefined}
	trail={!application && !complete ? trail : undefined}
	{hint}
	actions={application?.status === 'running' ? undefined : actions}
/>
