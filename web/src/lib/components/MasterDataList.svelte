<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import ContactAvatar from '#lib/components/ContactAvatar.svelte';
	import MasterPages from '#lib/components/MasterPages.svelte';
	import MasterRow from '#lib/components/MasterRow.svelte';
	import PanelState from '#lib/components/PanelState.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import TypeAvatar from '#lib/components/TypeAvatar.svelte';
	import { desktop } from '#lib/desktop.svelte.ts';
	import { describeError } from '#lib/errors.ts';
	import { latest } from '#lib/latest.ts';
	import { sortItems, type MasterSort } from '#lib/master-pages.ts';
	import { contactMatches, typeMatches } from '#lib/master-search.ts';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { type Item, KINDS } from '#lib/masterdata-api.ts';
	import type { FieldDefinition, Tag, TagScope } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import { scope } from '#lib/scope.svelte.ts';
	import { below, pathLabel } from '#lib/tags.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import Chip from '#lib/components/Chip.svelte';

	// Contacts (with their logo or initials, groups, aliases, identifiers, topics) or document
	// types (with their icon, description, groups, fields, title pattern, whether a relation
	// target), found by the search of the page, in the order of `sort`, a page at a time
	// (`MasterPages`). A link from the Tags tab lists the contacts of a group or topic, the types
	// of a group (`?group=`, `?topic=`, with the ones below it). A row opens the editor.
	//
	// Both rows are built alike (Tobi, 12.11.2026): the avatar, the name and under it what the
	// item is (a contact's other spelling, a type's description); on a desktop its groups and
	// what else it holds in columns of their own that line up from row to row, narrower all of it
	// in the line under the name; on a phone the first group and what it is.
	let {
		kind,
		query = '',
		sort = 'name'
	}: { kind: 'contacts' | 'document-types'; query?: string; sort?: MasterSort } = $props();
	const ops = $derived(KINDS[kind]);

	let items = $state<Item[] | null>(null);
	let tags = $state<Tag[]>([]);
	let fields = $state<FieldDefinition[]>([]);
	let problem = $state<string | null>(null);

	const byId = $derived(new Map(tags.map((tag) => [tag.id, tag])));
	/** `id` if it names a tag of `scope`; else null: the filter is ignored. */
	function known(id: string | null, scope: TagScope): string | null {
		return id !== null && byId.get(id)?.scope === scope ? id : null;
	}
	const group = $derived(
		known(page.url.searchParams.get('group'), kind === 'contacts' ? 'contact' : 'document_type')
	);
	const topic = $derived(
		kind === 'contacts' ? known(page.url.searchParams.get('topic'), 'topic') : null
	);
	const filterTag = $derived(byId.get(group ?? topic ?? '') ?? null);
	const listed = $derived.by(() => {
		let list = items ?? [];
		const within = (wanted: string, ids: readonly string[] | undefined) => {
			const tree = below(tags, wanted).add(wanted);
			return (ids ?? []).some((id) => tree.has(id));
		};
		if (group) list = list.filter((item) => within(group, item.group_ids));
		if (topic) list = list.filter((item) => within(topic, item.topic_ids));
		if (query.trim()) {
			list = list.filter((item) =>
				kind === 'contacts' ? contactMatches(item, query) : typeMatches(item, query)
			);
		}
		return sortItems(list, sort);
	});

	const begin = latest();
	async function load() {
		const current = begin();
		try {
			const found = await Promise.all([
				ops.list({ counts: true, allUsers: scope.allUsers }),
				unwrap(api.GET('/api/v1/tags')),
				kind === 'document-types' ? unwrap(api.GET('/api/v1/fields')) : Promise.resolve([])
			]);
			if (!current()) return;
			[items, tags, fields] = found;
			problem = null;
		} catch (error) {
			if (current()) problem = describeError(error);
		}
	}

	// Once the tags are there, a filter naming no tag of its kind (deleted, mistyped) leaves the
	// URL instead of emptying the list without a chip to remove.
	$effect(() => {
		if (items === null) return;
		const params = page.url.searchParams;
		const stale =
			(params.has('group') && group === null) ||
			(kind === 'contacts' && params.has('topic') && topic === null);
		if (!stale) return;
		const kept = [`tab=${kind}`, group && `group=${group}`, topic && `topic=${topic}`];
		void goto(`?${kept.filter(Boolean).join('&')}`, { replace: true, reset: false });
	});

	// A link to a document type opens it.
	onMount(() => {
		const wanted = kind === 'document-types' ? page.url.searchParams.get('type') : null;
		if (wanted) masterDataDialogs.open('document-types', wanted);
	});

	// Again after a dialog saved (wherever it was opened), and with another scope.
	$effect(() => {
		void masterDataDialogs.changed;
		void scope.allUsers;
		void load();
	});

	/** An item's groups, by path. */
	function groupsOf(item: Item): Tag[] {
		return (item.group_ids ?? [])
			.map((id) => byId.get(id))
			.filter((tag): tag is Tag => tag !== undefined)
			.sort((a, b) => pathLabel(a).localeCompare(pathLabel(b)));
	}

	interface Fact {
		text: string;
		/** Said in full as its tooltip (a title pattern). */
		title?: string;
	}

	/** What the item is, under its name: a contact's other spelling, a type's description. */
	function aboutOf(item: Item): string | null {
		if (kind === 'document-types') return item.description || null;
		const aliases = item.aliases ?? [];
		if (aliases.length === 0) return null;
		return aliases.length === 1
			? m.master_alias_short({ alias: aliases[0] })
			: m.master_alias_more({ alias: aliases[0], count: aliases.length - 1 });
	}

	/** What else it holds: a contact's identifiers and topics; a type's fields, its title pattern
	 * (in full as tooltip) and whether a relation target. */
	function factsOf(item: Item): Fact[] {
		const facts: (Fact | null)[] = [];
		if (kind === 'contacts') {
			const identifiers = (item.identifiers ?? []).filter((entry) => entry.source !== 'rejected');
			const topics = item.topic_ids?.length ?? 0;
			facts.push(
				identifiers.length === 0
					? null
					: {
							text:
								identifiers.length === 1
									? m.master_identifier_one()
									: m.master_identifiers_many({ count: identifiers.length })
						},
				topics === 0
					? null
					: { text: topics === 1 ? m.master_topic_one() : m.master_topics_many({ count: topics }) }
			);
		} else {
			const fieldsText = fieldsNote(item);
			facts.push(
				fieldsText ? { text: fieldsText } : null,
				item.title_pattern ? { text: m.master_title_pattern(), title: item.title_pattern } : null,
				item.relation_target ? { text: m.master_relation_target() } : null
			);
		}
		return facts.filter((fact) => fact !== null);
	}

	/** A type's own fields, and how many of them are required. */
	function fieldsNote(item: Item): string | null {
		const own = fields.filter((field) => field.document_type_ids?.includes(item.id));
		if (own.length === 0) return null;
		const required = own.filter((field) => field.required_document_type_ids.includes(item.id));
		const count =
			own.length === 1 ? m.master_field_one() : m.master_fields_many({ count: own.length });
		return required.length > 0
			? m.master_fields_required({
					fields: count,
					required: m.master_required_count({ count: required.length })
				})
			: count;
	}
</script>

<div class="flex flex-col gap-3">
	{#if filterTag}
		{@const label =
			group !== null
				? m.master_filter_group({ name: pathLabel(filterTag) })
				: m.master_filter_topic({ name: pathLabel(filterTag) })}
		<div>
			<Chip
				variant="selected"
				removeLabel={m.master_filter_remove({ name: label })}
				onremove={() => goto(`?tab=${kind}`, { reset: false })}>{label}</Chip
			>
		</div>
	{/if}
	<PanelState
		{problem}
		loading={!items}
		empty={listed.length > 0
			? null
			: items?.length === 0
				? m.master_none()
				: m.assignment_none_found()}
		onretry={load}
	>
		<MasterPages items={listed} table={kind} {query}>
			{#snippet children(shown)}
				<Card.Root as="ul" size="flush" class="divide-y overflow-hidden" aria-label={ops.title()}>
					{#each shown as item (item.id)}
						{@const groups = groupsOf(item)}
						{@const about = aboutOf(item)}
						{@const facts = factsOf(item)}
						<MasterRow
							columns
							onopen={() => masterDataDialogs.open(kind, item)}
							editLabel={m.master_edit({ name: item.name })}
							usage={[
								{ count: item.document_count, href: `${BASE}/documents?${ops.filter}=${item.id}` }
							]}
						>
							{#snippet lead()}
								{#if kind === 'contacts'}
									<ContactAvatar contact={item} size="md" class="max-sm:size-10 max-sm:text-sm" />
								{:else}
									<TypeAvatar icon={item.icon} class="max-sm:size-10 max-sm:[&_svg]:size-5" />
								{/if}
							{/snippet}
							{#if phone.current}
								<span class="line-clamp-2 break-words">{item.name}</span>
								{#if groups.length > 0 || about}
									<span
										class="flex min-h-6 w-full min-w-0 items-center gap-1.5 text-sm text-muted-foreground"
									>
										{#if groups.length > 0}
											<span class="flex max-w-2/3 shrink-0 items-center gap-1.5">
												{@render groupChips(groups, 1)}
											</span>
										{/if}
										{#if about}<span class="min-w-0 truncate">{about}</span>{/if}
									</span>
								{/if}
							{:else if desktop.current}
								<span class="flex w-full min-w-0 items-center gap-3">
									<span class="flex min-w-0 flex-1 flex-col gap-1">
										<span class="truncate" title={item.name}>{item.name}</span>
										{#if about}
											<span class="truncate text-sm text-muted-foreground">{about}</span>
										{/if}
									</span>
									<span class="flex w-50 shrink-0 items-center gap-1.5 overflow-hidden">
										{@render groupChips(groups, 2)}
									</span>
									<span class="w-60 shrink-0 truncate text-sm text-muted-foreground">
										{@render line(facts)}
									</span>
								</span>
							{:else}
								<span class="w-full truncate" title={item.name}>{item.name}</span>
								{#if groups.length > 0 || about || facts.length > 0}
									<span
										class="flex min-h-6 w-full min-w-0 items-center gap-2 text-sm text-muted-foreground"
									>
										{#if groups.length > 0}
											<span class="flex max-w-2/3 shrink-0 items-center gap-1.5">
												{@render groupChips(groups, 2)}
											</span>
										{/if}
										<span class="min-w-0 truncate">
											{@render line(about ? [{ text: about }, ...facts] : facts)}
										</span>
									</span>
								{/if}
							{/if}
						</MasterRow>
					{/each}
				</Card.Root>
			{/snippet}
		</MasterPages>
	</PanelState>
</div>

<!-- The first `room` groups as chips, the count of the others after them. -->
{#snippet groupChips(groups: Tag[], room: number)}
	{#each groups.slice(0, room) as tag (tag.id)}<TagChip {tag} group size="sm" />{/each}
	{#if groups.length > room}
		<span class="shrink-0 text-xs" title={groups.slice(room).map(pathLabel).join(', ')}>
			{m.master_groups_more({ count: groups.length - room })}
		</span>
	{/if}
{/snippet}

<!-- Facts in a line, a dot between them (a comma to a screen reader). -->
{#snippet line(facts: Fact[])}
	{#each facts as fact, index (fact.text)}
		{#if index > 0}<span class="sr-only">, </span><span class="px-1.5" aria-hidden="true">·</span
			>{/if}<span title={fact.title}>{fact.text}</span>
	{/each}
{/snippet}
