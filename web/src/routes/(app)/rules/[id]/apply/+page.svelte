<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
	import { onDestroy, untrack } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import { BASE } from '#lib/base.ts';
	import BulkSkipped from '#lib/components/BulkSkipped.svelte';
	import EmptyNote from '#lib/components/EmptyNote.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import RuleApplyBar from '#lib/components/rules/RuleApplyBar.svelte';
	import RuleEffectChange from '#lib/components/rules/RuleEffectChange.svelte';
	import RuleEffects from '#lib/components/rules/RuleEffects.svelte';
	import DocumentThumb from '#lib/components/DocumentThumb.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import NamesLine from '#lib/components/NamesLine.svelte';
	import { bulkDocuments } from '#lib/bulk.ts';
	import { formatDate } from '#lib/i18n.ts';
	import BeamTitle from '#lib/components/BeamTitle.svelte';
	import { openBeam } from '#lib/beam.svelte.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { workersStill, type JobsSummary } from '#lib/jobs.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { canApplyRule, canChangeRule } from '#lib/permissions.ts';
	import { phone } from '#lib/phone.svelte.ts';
	import {
		ahead,
		applicationResult,
		applyRequest,
		chainLines,
		follow,
		groupPreview,
		hasConflict,
		ownEffects,
		isFinished,
		preselected,
		type Application,
		type PreviewItem
	} from '#lib/rules/apply.ts';
	import { RuleLoader } from '#lib/rules/page.svelte.ts';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import { Choice, ChoiceBox } from '#lib/components/ui/choice/index.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import * as Card from '#lib/components/ui/card/index.ts';
	import Loading from '#lib/components/Loading.svelte';

	// A rule's dry run (web/DESIGN.md, "Choosing many"): what its current version would change on
	// existing documents, loaded page by page until all are there or the reader stops it; the
	// choice and the actions in the bar (`RuleApplyBar`), the rule's switch in the head. Applying
	// runs in the background; the bar follows it, and the link keeps it (`?application=`), so that
	// coming back shows it again.
	type Rule = components['schemas']['RuleOut'];
	const PAGE = 50;
	/** How often a queued application asks what comes before it. */
	const QUEUE_POLL = 5000;

	const id = $derived(page.params.id ?? '');
	/** Right after saving (decision E2): saved switched off, to switch on here or leave off. */
	const saved = $derived(page.url.searchParams.get('saved') === '1');

	let rule = $state<Rule | null>(null);
	const loader = new RuleLoader();
	const lookup = $derived(loader.lookup);
	const problem = $derived(loader.problem);
	let items = $state<PreviewItem[]>([]);
	let version = $state<number | null>(null);
	let cursor = $state<string | null>(null);
	let complete = $state(false);
	/** Documents the dry run has looked at so far, those without a change among them. */
	let lookedAt = $state(0);
	/** What the whole dry run looks at: the documents the rule's conditions leave. */
	let total = $state<number | null>(null);
	/** The dry run was started (coming back to an application shows none). */
	let started = $state(false);
	let loading = $state(false);
	let loadingAll = $state(false);
	let previewError = $state<string | null>(null);
	const chosen = new SvelteSet<string>();
	const accepted = new SvelteSet<string>();
	let busy = $state(false);
	let application = $state<Application | null>(null);
	let summary = $state<JobsSummary | null>(null);
	let details = $state<Application | null>(null);
	const stop = new AbortController();
	onDestroy(() => stop.abort());

	const spaces = $derived(lookup?.spaces ?? []);
	const changeable = $derived(rule !== null && canChangeRule(rule, session.user, spaces));
	const request = $derived(
		version === null ? null : applyRequest(version, items, chosen, accepted)
	);
	const count = $derived(request?.document_ids.length ?? 0);
	const plain = $derived(items.filter((item) => !hasConflict(item)));
	/** The documents by what the rule changes on them (web/DESIGN.md, "A rule's dry run"). */
	const groups = $derived(groupPreview(items));
	/** The groups folded away, by key. */
	const folded = new SvelteSet<string>();
	const allChosen = $derived(
		plain.length > 0 && plain.every((item) => chosen.has(item.document_id))
	);
	const waiting = $derived(
		application?.status === 'queued' && summary
			? { jobs: ahead(summary), still: workersStill(summary) }
			: null
	);
	// From the start of the dry run: rules that hit few documents look at many pages first.
	const showBar = $derived(
		application !== null || items.length > 0 || (started && !complete && !previewError)
	);

	$effect(() => {
		const wanted = id;
		const following = untrack(() => page.url.searchParams.get('application'));
		untrack(() =>
			loader.load(
				() => unwrap(api.GET('/api/v1/rules/{id}', { params: { path: { id: wanted } } })),
				(found, loaded) => {
					rule = found;
					// Only who may apply the rule gets its preview (the API refuses the others).
					if (!canApplyRule(found, session.user, loaded.spaces)) {
						loader.problem = m.error_forbidden();
						return;
					}
					if (following) void resume(following);
					else start();
				}
			)
		);
	});

	/** The dry run from its start, every page of it. */
	function start() {
		started = true;
		restart();
		void all();
	}

	function restart() {
		items = [];
		version = null;
		cursor = null;
		complete = false;
		lookedAt = 0;
		total = null;
		chosen.clear();
		accepted.clear();
	}

	// The request in flight: a second call joins it instead of starting another.
	let pending: Promise<void> | null = null;

	/** The next page. It may hold no document and still have a next one. */
	function more(): Promise<void> {
		pending ??= nextPage().finally(() => (pending = null));
		return pending;
	}

	async function nextPage(): Promise<void> {
		if (complete) return;
		loading = true;
		previewError = null;
		try {
			const preview = await unwrap(
				api.POST('/api/v1/rules/{id}/apply/preview', {
					params: { path: { id } },
					body: { cursor, limit: PAGE }
				})
			);
			if (version !== null && preview.version !== version) {
				// The rule changed between pages: what was loaded no longer holds.
				restart();
				toast.info(m.rule_preview_restarted());
				return;
			}
			version = preview.version;
			lookedAt += preview.looked_at;
			total = preview.total;
			items = [...items, ...preview.items];
			for (const documentId of preselected(preview.items)) chosen.add(documentId);
			cursor = preview.next_cursor;
			complete = cursor === null;
		} catch (error) {
			previewError = describeError(error);
		} finally {
			loading = false;
		}
	}

	/** Page after page until all are there, the reader stops it or a page fails. */
	async function all() {
		loadingAll = true;
		while (loadingAll && !complete && !previewError && !stop.signal.aborted) await more();
		loadingAll = false;
	}

	async function setEnabled(enabled: boolean) {
		rule = await unwrap(
			api.PATCH('/api/v1/rules/{id}', { params: { path: { id } }, body: { enabled } })
		);
	}

	async function switchRule(enabled: boolean) {
		busy = true;
		try {
			await setEnabled(enabled);
			toast.success(enabled ? m.rule_switched_on() : m.rule_switched_off());
		} catch (error) {
			reportError(error);
		} finally {
			busy = false;
		}
	}

	async function apply(switchOn: boolean) {
		if (!request) return;
		busy = true;
		try {
			if (switchOn) await setEnabled(true);
			const started = await unwrap(
				api.POST('/api/v1/rules/{id}/apply', { params: { path: { id } }, body: request })
			);
			void goto(`?application=${started.id}`, { replace: true, reset: false });
			busy = false;
			await track(started);
		} catch (error) {
			reportError(error);
		} finally {
			busy = false;
		}
	}

	/** Back on the page of an application started before: its progress, else a new dry run. */
	async function resume(applicationId: string) {
		try {
			const found = await unwrap(
				api.GET('/api/v1/rule-applications/{id}', { params: { path: { id: applicationId } } })
			);
			if (found.rule_id === id) {
				await track(found);
				return;
			}
		} catch (error) {
			reportError(error);
		}
		start();
	}

	/** Follow `started` until it is finished; one that finishes meanwhile says so in a toast. */
	async function track(started: Application) {
		application = started;
		void watchQueue();
		try {
			const last = await follow(
				started,
				(applicationId) =>
					unwrap(
						api.GET('/api/v1/rule-applications/{id}', { params: { path: { id: applicationId } } })
					),
				(current) => (application = current),
				stop.signal
			);
			if (!isFinished(started) && isFinished(last) && !stop.signal.aborted) tell(last);
		} catch (error) {
			reportError(error);
		}
	}

	/** While the application waits: what comes before it and whether a worker takes jobs. */
	async function watchQueue() {
		while (application?.status === 'queued' && !stop.signal.aborted) {
			try {
				summary = await unwrap(api.GET('/api/v1/jobs/summary'));
			} catch {
				// The bar says less until the next round.
			}
			await new Promise((resolve) => setTimeout(resolve, QUEUE_POLL));
		}
	}

	function tell(last: Application) {
		const result = applicationResult(last);
		if (last.status === 'failed') {
			toast.error(m.rule_apply_failed(), { description: last.error ?? result });
		} else if (last.skipped.length > 0) {
			toast.warning(m.rule_apply_done(), {
				description: result,
				action: { label: m.bulk_details(), onClick: () => (details = last) }
			});
		} else {
			toast.success(m.rule_apply_done(), { description: result });
		}
	}

	function choose(item: PreviewItem, on: boolean) {
		const set = hasConflict(item) ? accepted : chosen;
		if (on) set.add(item.document_id);
		else set.delete(item.document_id);
	}

	/** Every document of a group without a conflict, or none of them. */
	function chooseGroup(members: readonly PreviewItem[], on: boolean) {
		for (const item of members) {
			if (on) chosen.add(item.document_id);
			else chosen.delete(item.document_id);
		}
	}

	function fold(key: string) {
		if (folded.has(key)) folded.delete(key);
		else folded.add(key);
	}

	function chooseAll(on: boolean) {
		if (on) for (const item of plain) chosen.add(item.document_id);
		else {
			chosen.clear();
			accepted.clear();
		}
	}
</script>

<svelte:head
	><title
		>{rule ? m.rule_apply_title({ name: rule.name }) : m.rule_apply_generic()} · {m.app_name()}</title
	></svelte:head
>

{#snippet switcher()}
	<Switch
		bind:checked={() => rule?.enabled ?? false, switchRule}
		disabled={busy}
		aria-label={rule?.enabled
			? m.rule_switch_off({ name: rule.name })
			: m.rule_switch_on({ name: rule?.name ?? '' })}
	/>
{/snippet}

{#snippet bar()}
	<RuleApplyBar
		chosen={count}
		{allChosen}
		{lookedAt}
		{total}
		loaded={items.length}
		conflicts={items.length - plain.length}
		loading={loadingAll}
		{complete}
		offerSwitchOn={changeable && rule?.enabled === false}
		{busy}
		{application}
		{waiting}
		rule={id}
		onchoose={chooseAll}
		onstop={() => (loadingAll = false)}
		onmore={() => void all()}
		onapply={(switchOn) => void apply(switchOn)}
		ondetails={(finished) => (details = finished)}
	/>
{/snippet}

<div class="flex flex-col gap-6">
	<PageHeader
		title={rule ? m.rule_apply_title({ name: rule.name }) : m.rule_apply_generic()}
		back={{ href: `${BASE}/rules/${id}`, label: rule?.name ?? m.nav_rules() }}
		actions={changeable ? switcher : undefined}
		subtitle={saved ? m.rule_saved_hint() : m.rule_apply_hint()}
	/>

	{#if problem}
		<LoadProblem {problem} onretry={() => loader.retry()} />
	{:else if !rule}
		<Loading />
	{:else}
		{#if showBar && !phone.current}{@render bar()}{/if}

		{#if items.length > 0}
			<div
				class={cn('flex flex-col gap-4', application && 'opacity-50')}
				inert={application !== null}
			>
				{#each groups as group (group.key)}
					{@const open = !folded.has(group.key)}
					{@const choosable = group.items.filter((item) => !hasConflict(item))}
					<Card.Root
						as="section"
						size="flush"
						class={cn('overflow-hidden', group.conflict && 'border-lane-yellow-foreground/35')}
						aria-label={bulkDocuments(group.items.length)}
					>
						<!-- The head: what the rule changes on all of them, said once. -->
						<div
							class={cn(
								'flex items-center gap-3 px-4 py-3',
								open && 'border-b',
								group.conflict ? 'bg-lane-yellow/40' : 'bg-muted/50'
							)}
						>
							{#if group.conflict}
								<TriangleAlert
									class="size-4 shrink-0 text-lane-yellow-foreground"
									aria-hidden="true"
								/>
							{:else}
								<ChoiceBox
									aria-label={m.rule_group_choose({
										documents: bulkDocuments(group.items.length)
									})}
									checked={choosable.every((item) => chosen.has(item.document_id))}
									onchange={(event) => chooseGroup(choosable, event.currentTarget.checked)}
								/>
							{/if}
							<div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1.5">
								{#each group.shared as effect (effect.field)}
									<RuleEffectChange
										field={effect.field}
										old={'old' in effect ? effect.old : undefined}
										next={effect.new}
										{lookup}
									/>
								{/each}
								{#if group.conflict}
									<Badge variant="yellow">{m.rule_conflict()}</Badge>
									{#if group.conflicts.length > 0}
										<div class="text-sm text-muted-foreground">
											<RuleEffects effects={[]} notes={group.conflicts} {lookup} />
										</div>
									{/if}
								{/if}
							</div>
							<span class="shrink-0 text-sm text-muted-foreground"
								>{bulkDocuments(group.items.length)}</span
							>
							<IconButton
								size="sm"
								label={open ? m.rule_group_fold() : m.rule_group_unfold()}
								aria-expanded={open}
								onclick={() => fold(group.key)}
							>
								<ChevronDown
									class={cn(
										'transition-transform motion-reduce:transition-none',
										open && 'rotate-180'
									)}
									aria-hidden="true"
								/>
							</IconButton>
						</div>
						{#if open}
							<ul class="divide-y">
								{#each group.items as item (item.document_id)}
									{@const conflict = hasConflict(item)}
									{@const picked = (conflict ? accepted : chosen).has(item.document_id)}
									{@const own = ownEffects(item, group)}
									{@const contact = lookup?.contacts.find((entry) => entry.id === item.contact_id)}
									{@const kind = lookup?.documentTypes.find(
										(entry) => entry.id === item.document_type_id
									)}
									<li class={cn('flex items-start gap-3 px-4 py-2.5', picked && 'bg-panel')}>
										{#if !conflict}
											<ChoiceBox
												class="mt-4"
												aria-label={m.rule_select_document({ title: item.title })}
												checked={picked}
												onchange={(event) => choose(item, event.currentTarget.checked)}
											/>
										{/if}
										<DocumentThumb
											id={item.document_id}
											pages={item.page_count}
											class="h-12 w-9 shrink-0 rounded-md border"
										/>
										<div class="flex min-w-0 flex-1 flex-col gap-1 text-sm">
											<!-- The title opens the Beam: where the rule's text conditions hit. -->
											<BeamTitle
												title={item.title}
												class="max-w-full text-base"
												onview={() =>
													openBeam(
														items.map((entry) => entry.document_id),
														item.document_id,
														rule ? m.rule_apply_title({ name: rule.name }) : m.rule_apply_generic(),
														{ source: { kind: 'rule', rule: id } }
													)}
											/>
											<NamesLine
												parts={[
													{ name: contact?.name, groupIds: contact?.group_ids, avatar: contact },
													{ name: kind?.name, groupIds: kind?.group_ids, icon: kind?.icon }
												]}
												date={formatDate(item.document_date ?? item.created_at)}
												tags={lookup?.tags ?? []}
												class="text-muted-foreground"
											/>
											{#if own.length > 0 || item.notes.length > 0 || (item.sends?.length ?? 0) > 0 || (item.sends_refused?.length ?? 0) > 0}
												<div class="text-muted-foreground">
													<RuleEffects
														effects={own}
														notes={item.notes}
														sends={item.sends}
														refused={item.sends_refused}
														{lookup}
													/>
												</div>
											{/if}
											{#if item.outcome.chain.length > 0}
												<ul class="flex flex-col gap-0.5">
													{#each chainLines(item.outcome, rule?.name ?? '', lookup, session.user?.id) as line, index (index)}
														<li>{line}</li>
													{/each}
												</ul>
											{/if}
											{#if conflict}
												{#if group.conflicts.length === 0}
													<RuleEffects effects={[]} notes={item.conflicts} {lookup} />
												{/if}
												{#if item.accepted && (item.accepted.chain.length > 0 || item.accepted.space_id !== item.outcome.space_id)}
													<p class="font-medium">{m.rule_chain_accepted()}</p>
													<ul class="flex flex-col gap-0.5">
														{#each chainLines(item.accepted, rule?.name ?? '', lookup, session.user?.id) as line, index (index)}
															<li>{line}</li>
														{/each}
													</ul>
												{/if}
												<Choice
													checked={picked}
													onchange={(event) => choose(item, event.currentTarget.checked)}
													class="font-medium"
												>
													{m.rule_accept_conflict()}
												</Choice>
											{/if}
										</div>
									</li>
								{/each}
							</ul>
						{/if}
					</Card.Root>
				{/each}
			</div>
		{:else if complete}
			<EmptyNote>{m.rule_preview_nothing()}</EmptyNote>
		{/if}

		{#if previewError}
			<LoadProblem problem={previewError} onretry={() => void all()} />
		{:else if loading && items.length === 0}
			<Loading />
		{/if}

		{#if showBar && phone.current}{@render bar()}{/if}
	{/if}
</div>

<BulkSkipped operation={details} onclose={() => (details = null)} />
