<script lang="ts">
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import Plus from '@lucide/svelte/icons/plus';
	import X from '@lucide/svelte/icons/x';
	import ScanEye from '@lucide/svelte/icons/scan-eye';
	import { tick } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { openBeam } from '#lib/beam.svelte.ts';
	import { describeError } from '#lib/errors.ts';
	import { formatNumber } from '#lib/i18n.ts';
	import { refOf } from '#lib/fact-refs.svelte.ts';
	import ContactAvatar from '#lib/components/ContactAvatar.svelte';
	import InfoHint from '#lib/components/InfoHint.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import Select from '#lib/components/Select.svelte';
	import TagPicker from '#lib/components/TagPicker.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import {
		IDENTIFIER_KINDS,
		type IdentifierKind,
		type IdentifierRow,
		type IdentifierSource,
		kindLabel,
		NAMING_KINDS,
		printed,
		row
	} from '#lib/identifiers.ts';
	import {
		type Contact,
		type Tag,
		userChoice,
		userName,
		type UserName
	} from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import Eyebrow from '#lib/components/page/Eyebrow.svelte';
	import IconButton from '#lib/components/IconButton.svelte';

	// A contact's identifiers, one line each under their kind (Tobi, 20.10.2026): the value, a
	// mark if learned or rejected, the topic it points to. A line opens with its arrow, one at a
	// time (`opened`): one entered by hand shows kind, value and topic, changed at once (saved
	// with the editor); a learned one can be taken over (then it is entered by hand) or
	// rejected (training does not learn it again); a rejected one can be allowed again. Enter
	// in the value closes the line. A search finds them by value, kind and topic; a new one
	// opens empty. `errors` (by row key) show in their open line. `kinds`: those offered (a
	// person's in the profile); `users`: a customer or personnel number may name the user it
	// belongs to, one of these (the contact dialog). `contacts`: the lines are a user's identifiers
	// at these contacts (the profile, issue #82): grouped by contact, one closed line each, which a
	// search opens where it finds something, and shown by source (Tobi, 02.11.2026); each offers
	// the topics its contact enables, and a learned one is taken over or declined as not theirs.
	let {
		rows = $bindable(),
		topics = [],
		opened = $bindable(null),
		errors = {},
		hint,
		kinds: offered = IDENTIFIER_KINDS,
		users = null,
		contacts
	}: {
		rows: IdentifierRow[];
		topics?: readonly Tag[];
		opened?: number | null;
		errors?: Record<number, string>;
		/** The help of the identifiers, behind an info button beside the search. */
		hint?: string;
		kinds?: readonly IdentifierKind[];
		/** Without the list, a number still shows whose it is by id; it only cannot be chosen. */
		users?: readonly UserName[] | null;
		contacts?: readonly ListedContact[];
	} = $props();

	type ListedContact = Pick<Contact, 'id' | 'name' | 'topic_ids'> & Partial<Pick<Contact, 'logo'>>;

	const uid = $props.id();
	let query = $state('');
	let source = $state<IdentifierSource | ''>('');
	let openGroups = $state<string[]>([]);
	const kinds = $derived(offered.map((kind) => ({ value: kind, label: kindLabel(kind) })));
	const withUsers = $derived(users !== null);
	const userOptions = $derived([
		{ value: '', label: m.identifier_user_none() },
		...(users ?? []).map((user) => ({ value: user.id, label: userChoice(user) }))
	]);
	const contactOptions = $derived([
		{ value: '', label: m.number_contact_choose() },
		...(contacts ?? []).map((contact) => ({ value: contact.id, label: contact.name }))
	]);
	const compact = (text: string) => text.replace(/\s+/g, '').toLocaleLowerCase();
	const found = $derived.by(() => {
		const wanted = compact(query);
		if (wanted === '') return rows;
		return rows.filter((item) =>
			compact(
				`${item.value} ${kindLabel(item.kind)} ${topicOf(item.topic_id)?.name ?? ''} ${
					contactOf(item)?.name ?? ''
				}`
			).includes(wanted)
		);
	});
	const shown = $derived(
		contacts && source !== '' ? found.filter((item) => item.source === source) : found
	);
	const SOURCE_LABELS = {
		'': m.numbers_all,
		learned: m.numbers_learned,
		manual: m.numbers_manual,
		rejected: m.numbers_rejected
	};
	const sources = $derived(
		(['', 'learned', 'manual', 'rejected'] as const).map((value) => ({
			value,
			label: SOURCE_LABELS[value](),
			count: formatNumber(
				value === '' ? found.length : found.filter((item) => item.source === value).length
			)
		}))
	);
	/** By contact: one group each, without contact first, then by name; the lines in the order of
	 * their kinds. */
	const byContact = $derived.by(() => {
		const order = (item: IdentifierRow) => offered.indexOf(item.kind as IdentifierKind);
		const named: Record<string, IdentifierRow[]> = {};
		for (const item of shown) (named[item.contact_id] ??= []).push(item);
		return Object.entries(named)
			.map(([id, items]) => ({
				id,
				contact: contactOf(items[0]),
				rows: items.toSorted((a, b) => order(a) - order(b)),
				kinds: [...new Set(items.toSorted((a, b) => order(a) - order(b)).map((item) => item.kind))]
					.map((kind) => kindLabel(kind as IdentifierKind))
					.join(', ')
			}))
			.toSorted((a, b) =>
				a.contact === null
					? -1
					: b.contact === null
						? 1
						: a.contact.name.localeCompare(b.contact.name)
			);
	});
	const groups = $derived(
		offered
			.map((kind) => ({
				kind,
				rows: shown.filter((item) => item.kind === kind)
			}))
			.filter((group) => group.rows.length > 0)
	);

	function topicOf(id: string): Tag | null {
		return topics.find((topic) => topic.id === id) ?? null;
	}

	function contactOf(item: IdentifierRow): ListedContact | null {
		return contacts?.find((contact) => contact.id === item.contact_id) ?? null;
	}

	/** The topics a line may point to: those its contact enables, for a user's number. */
	function topicsFor(item: IdentifierRow): readonly Tag[] {
		if (!contacts) return topics;
		const enabled = contactOf(item)?.topic_ids ?? [];
		return topics.filter((topic) => enabled.includes(topic.id));
	}

	function indexOf(item: IdentifierRow): number {
		return rows.findIndex((other) => other.key === item.key);
	}

	/** Where a learned one stands: the documents within reach that show it, in the Beam, each
	 * place marked. */
	async function whence(item: IdentifierRow) {
		const kind = item.kind as IdentifierKind;
		try {
			const ref = await refOf(kind, item.value);
			const found = await unwrap(
				api.GET('/api/v1/identifiers/places/{kind}/{ref}', {
					params: { path: { kind, ref } }
				})
			);
			const ids = found.places.map((place) => place.document_id);
			if (ids.length === 0) {
				toast.info(m.identifier_whence_none());
				return;
			}
			openBeam(ids, ids[0], `${kindLabel(kind)} ${printed(kind, item.value)}`, {
				source: { kind: 'places', identifier: kind, ref }
			});
		} catch (error) {
			toast.error(describeError(error));
		}
	}

	function become(item: IdentifierRow, source: IdentifierSource) {
		rows = rows.map((other) => (other.key === item.key ? { ...other, source } : other));
	}

	function drop(item: IdentifierRow) {
		rows = rows.filter((other) => other.key !== item.key);
		if (opened === item.key) opened = null;
	}

	/** Whether a contact's group shows its lines: opened, a search, or the line opened in it. */
	function isOpen(group: { id: string; rows: IdentifierRow[] }): boolean {
		return (
			query.trim() !== '' ||
			openGroups.includes(group.id) ||
			group.rows.some((item) => item.key === opened)
		);
	}

	function toggle(group: { id: string; rows: IdentifierRow[] }) {
		if (isOpen(group)) {
			openGroups = openGroups.filter((id) => id !== group.id);
			if (group.rows.some((item) => item.key === opened)) opened = null;
		} else {
			openGroups = [...openGroups, group.id];
		}
	}

	async function add() {
		const fresh = row(offered[0]);
		query = '';
		source = '';
		rows = [...rows, fresh];
		opened = fresh.key;
		await tick();
		document.getElementById(`${uid}-${fresh.key}-value`)?.focus();
	}

	function closeOnEnter(event: KeyboardEvent) {
		if (event.key !== 'Enter') return;
		// Not the editor's form: Enter only closes the line.
		event.preventDefault();
		opened = null;
	}
</script>

{#snippet value(item: IdentifierRow)}
	<span
		class={[
			'min-w-0 flex-1 truncate',
			item.value ? 'font-mono text-sm' : 'text-sm text-muted-foreground',
			item.source === 'rejected' && 'text-muted-foreground line-through'
		]}
	>
		{item.value ? printed(item.kind, item.value) : m.identifier_new()}
	</span>
{/snippet}

{#snippet line(item: IdentifierRow)}
	{@const open = opened === item.key}
	{@const topic = topicOf(item.topic_id)}
	{@const index = indexOf(item)}
	<li>
		<div class={['flex items-center gap-1 pr-1', open && 'bg-secondary/60']}>
			<button
				type="button"
				class={[
					'flex min-h-11 min-w-0 flex-1 items-center gap-2.5 py-1.5 text-left',
					contacts ? 'pl-9 sm:pl-15' : 'pl-3'
				]}
				aria-expanded={open}
				aria-controls={open ? `${uid}-${item.key}` : undefined}
				onclick={() => (opened = open ? null : item.key)}
			>
				<ChevronRight
					class={[
						'size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none',
						open && 'rotate-90 text-foreground'
					]}
					aria-hidden="true"
				/>
				{#if contacts}
					<!-- Their contact is the group's: the kind instead, above the value on a phone. -->
					<span class="flex min-w-0 flex-1 flex-col sm:flex-row sm:items-center sm:gap-2.5">
						<span class="truncate text-xs text-muted-foreground sm:w-52 sm:shrink-0 sm:text-sm">
							{kindLabel(item.kind as IdentifierKind)}
						</span>
						{@render value(item)}
					</span>
				{:else}
					{@render value(item)}
				{/if}
				{#if item.source !== 'manual'}
					<Badge variant={item.source === 'learned' ? 'note' : 'muted'}>
						{item.source === 'learned' ? m.identifier_learned() : m.identifier_rejected()}
					</Badge>
				{/if}
				{#if topic}<TagChip tag={topic} topic size="sm" />{/if}
				{#if withUsers && item.user_id}
					<Badge variant="outline">{userName(users ?? [], item.user_id)}</Badge>
				{/if}
				{#if errors[item.key]}
					<span class="size-[7px] shrink-0 rounded-full bg-destructive" aria-hidden="true"></span>
				{/if}
			</button>
			{#if item.source === 'manual'}
				<IconButton
					type="button"
					class="shrink-0"
					label={m.identifier_remove_named({
						value: item.value ? printed(item.kind, item.value) : m.identifier_new()
					})}
					onclick={() => drop(item)}
				>
					<X aria-hidden="true" />
				</IconButton>
			{:else}
				<span class="size-9 shrink-0" aria-hidden="true"></span>
			{/if}
		</div>
		{#if open}
			<div
				id="{uid}-{item.key}"
				class={['border-t bg-secondary/30 px-3 py-3', contacts ? 'border-b sm:pl-21' : 'sm:pl-10']}
			>
				{#if item.source === 'manual'}
					{#if contacts}
						<div class="mb-2 grid items-center gap-2 sm:grid-cols-[12.5rem_minmax(0,1fr)]">
							<span class="text-sm text-muted-foreground">{m.number_contact()}</span>
							<Select
								bind:value={rows[index].contact_id}
								options={contactOptions}
								aria-label={m.number_contact()}
							/>
						</div>
					{/if}
					{@const ownTopics = topicsFor(item)}
					<div
						class={[
							'grid gap-2',
							ownTopics.length > 0 || item.topic_id !== ''
								? 'sm:grid-cols-[12.5rem_minmax(0,1fr)_minmax(0,12rem)]'
								: 'sm:grid-cols-[12.5rem_minmax(0,1fr)]'
						]}
					>
						<Select
							bind:value={rows[index].kind}
							options={kinds}
							aria-label={m.identifier_kind()}
						/>
						<Input
							id="{uid}-{item.key}-value"
							bind:value={rows[index].value}
							aria-label={m.identifier_value()}
							aria-invalid={errors[item.key] ? true : undefined}
							maxlength={100}
							class="font-mono"
							onkeydown={closeOnEnter}
						/>
						{#if ownTopics.length > 0 || item.topic_id !== ''}
							<!-- The one choice of a topic, as at a document; one the contact no longer
							     enables stays as its chip, to be removed. -->
							<TagPicker
								id="{uid}-{item.key}-topic"
								label={m.identifier_topic()}
								title={m.picker_title_topic()}
								scope="topic"
								tags={topics}
								selected={item.topic_id === '' ? [] : [item.topic_id]}
								onchange={(next) => (rows[index].topic_id = next[0] ?? '')}
								offered={(tag) => ownTopics.some((own) => own.id === tag.id)}
								creating={false}
								single
							/>
						{/if}
					</div>
					{#if withUsers && NAMING_KINDS.includes(item.kind)}
						<div class="mt-2 grid items-center gap-2 sm:grid-cols-[12.5rem_minmax(0,1fr)]">
							<span class="text-sm text-muted-foreground">{m.identifier_user()}</span>
							<Select
								bind:value={rows[index].user_id}
								options={userOptions}
								aria-label={m.identifier_user()}
							/>
						</div>
					{/if}
					{#if errors[item.key]}
						<p class="mt-2 text-sm text-destructive" role="alert">{errors[item.key]}</p>
					{/if}
				{:else}
					<div class="flex flex-wrap items-center gap-x-3 gap-y-2">
						<p class="min-w-48 flex-1 text-sm text-muted-foreground">
							{#if contacts}
								{item.source === 'learned' ? m.number_learned_note() : m.number_declined_note()}
							{:else}
								{item.source === 'learned'
									? m.identifier_learned_note()
									: m.identifier_rejected_note()}
							{/if}
						</p>
						{#if item.source === 'learned'}
							<Button type="button" variant="ghost" size="sm" onclick={() => whence(item)}>
								<ScanEye aria-hidden="true" />
								{m.identifier_whence()}
							</Button>
							<Button
								type="button"
								variant="outline"
								size="sm"
								onclick={() => become(item, 'manual')}
							>
								{m.identifier_keep()}
							</Button>
							<Button
								type="button"
								variant="outline"
								size="sm"
								onclick={() => become(item, 'rejected')}
							>
								{contacts ? m.number_not_mine() : m.identifier_reject()}
							</Button>
						{:else if contacts}
							<Button
								type="button"
								variant="outline"
								size="sm"
								onclick={() => become(item, 'learned')}
							>
								{m.number_undo()}
							</Button>
						{:else}
							<Button type="button" variant="outline" size="sm" onclick={() => drop(item)}>
								{m.identifier_unblock()}
							</Button>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</li>
{/snippet}

<div class="flex flex-col gap-1" role="group" aria-label={m.master_identifiers()}>
	<div class="flex flex-wrap items-center gap-2 pb-1">
		{#if contacts}
			<Segmented
				bind:value={source}
				options={sources}
				label={m.numbers_source()}
				class="max-sm:w-full"
			/>
		{/if}
		<!-- Search, help and adding wrap as one, under the source where the row is narrow. -->
		<div class="flex min-w-72 flex-1 items-center gap-2">
			<SearchField bind:value={query} label={m.identifier_search()} class="flex-1" />
			{#if hint}<InfoHint text={hint} about={m.master_identifiers()} />{/if}
			{#if phone.current}
				<IconButton type="button" class="shrink-0" label={m.identifier_add()} onclick={add}>
					<Plus class="size-5" aria-hidden="true" />
				</IconButton>
			{:else}
				<Button type="button" variant="outline" class="h-10 shrink-0" onclick={add}>
					<Plus aria-hidden="true" />
					{m.identifier_add_short()}
				</Button>
			{/if}
		</div>
	</div>

	{#if rows.length === 0}
		<p class="rounded-2xl border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
			{m.identifier_none()}
		</p>
	{:else if (contacts ? byContact : groups).length === 0}
		<p class="px-1 py-2 text-sm text-muted-foreground">{m.assignment_none_found()}</p>
	{/if}

	{#if contacts}
		{#if byContact.length > 0}
			<Card.Root as="ul" size="flush" class="divide-y overflow-hidden">
				{#each byContact as group (group.id)}
					{@const open = isOpen(group)}
					<li>
						<button
							type="button"
							class="flex min-h-14 w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/50"
							aria-expanded={open}
							aria-controls={open ? `${uid}-contact-${group.id}` : undefined}
							onclick={() => toggle(group)}
						>
							<ChevronRight
								class={[
									'size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none',
									open && 'rotate-90 text-foreground'
								]}
								aria-hidden="true"
							/>
							{#if group.contact}
								<ContactAvatar contact={group.contact} size="md" />
							{:else}
								<span class="size-8 shrink-0 rounded-full border border-dashed" aria-hidden="true"
								></span>
							{/if}
							<span class="flex min-w-0 flex-1 flex-col gap-0.5">
								<span class="truncate text-sm font-medium"
									>{group.contact?.name ?? m.number_contact_none()}</span
								>
								<span class="text-xs text-muted-foreground">{group.kinds}</span>
							</span>
							<span class="shrink-0 text-meta text-muted-foreground tabular-nums" aria-hidden="true"
								>{group.rows.length}</span
							>
							<span class="sr-only"
								>{group.rows.length === 1
									? m.master_identifier_one()
									: m.master_identifiers_many({ count: group.rows.length })}</span
							>
						</button>
						{#if open}
							<ul id="{uid}-contact-{group.id}" class="pb-2">
								{#each group.rows as item (item.key)}
									{@render line(item)}
								{/each}
							</ul>
						{/if}
					</li>
				{/each}
			</Card.Root>
		{/if}
	{:else}
		{#each groups as group (group.kind)}
			<Eyebrow as="h3" class="flex items-baseline gap-2 px-1 pt-2 pb-1">
				{kindLabel(group.kind)}
				<span class="font-medium tabular-nums">{group.rows.length}</span>
			</Eyebrow>
			<Card.Root as="ul" size="flush" class="divide-y overflow-hidden">
				{#each group.rows as item (item.key)}
					{@render line(item)}
				{/each}
			</Card.Root>
		{/each}
	{/if}
</div>
