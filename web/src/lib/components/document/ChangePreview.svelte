<script lang="ts">
	import type { components } from '#lib/api/schema.ts';
	import { fieldText } from '#lib/card-fields.ts';
	import DetailList, { type DetailRow } from '#lib/components/DetailList.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import RuleEffects from '#lib/components/rules/RuleEffects.svelte';
	import TagChip from '#lib/components/TagChip.svelte';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { cardVariants } from '#lib/components/ui/card/index.ts';
	import { describeValue, fieldLabel } from '#lib/describe.ts';
	import { formatDate, listLocale } from '#lib/i18n.ts';
	import { spaceNameFor, userName, type Lookup } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';
	import { cn } from '#lib/utils.ts';

	type Document = components['schemas']['DocumentDetails'];
	type Preview = components['schemas']['DocumentPreviewOut'];
	type Member = components['schemas']['MemberOut'];

	// What a change of a document would do, before it is saved (web/DESIGN.md, "Change preview"):
	// each changed field with its value before and after (a removed tag red and struck through,
	// an added one green), the rules it sets off, and who sees the document then: one quiet line while
	// that stays as it was, the space and the people with who is new and who no longer sees it
	// when it changes.
	let { before, preview, lookup }: { before: Document; preview: Preview; lookup: Lookup | null } =
		$props();

	const after = $derived(preview.document);

	/** A field's value as the document shows it, null when it has none. */
	function shown(document: Document | null, key: string): string | null {
		if (!document) return null;
		if (key === 'title') return document.title;
		if (key === 'document_date')
			return document.document_date ? formatDate(document.document_date) : null;
		const ids: Record<string, string | null | undefined> = {
			contact: document.contact_id,
			document_type: document.document_type_id,
			topic: document.topic_id
		};
		if (key in ids) return ids[key] ? describeValue(ids[key], lookup) : null;
		if (key.startsWith('field:')) {
			const id = key.slice('field:'.length);
			const value = (document.fields as Record<string, unknown> | undefined)?.[id];
			if (value === null || value === undefined || value === '') return null;
			const field = lookup?.fields.find((entry) => entry.id === id);
			if (field?.data_type === 'date' && typeof value === 'string') return formatDate(value);
			return field ? fieldText(value, field) : describeValue(value, lookup);
		}
		return null;
	}

	const tagsOf = (document: Document | null) => document?.tag_ids ?? [];
	const removedTags = $derived(tagsOf(before).filter((id) => !tagsOf(after).includes(id)));
	const addedTags = $derived(tagsOf(after).filter((id) => !tagsOf(before).includes(id)));
	const tag = (id: string) =>
		lookup?.tags.find((entry) => entry.id === id) ?? {
			id,
			name: describeValue(id, lookup),
			path: []
		};

	// Each changed field but the space: that one is said with who sees it.
	const rows = $derived(
		preview.changed
			.filter((key) => key !== 'space')
			.map((key): DetailRow => [fieldLabel(key, lookup), fieldChange, key])
	);

	// Who sees it before (the members of its space now) and after.
	const visibility = $derived(preview.visibility);
	const membersBefore = $derived(
		lookup?.spaces.find((space) => space.id === before.space_id)?.members ?? []
	);
	const membersAfter = $derived(visibility?.members ?? []);
	const key = (member: Member) => `${member.user_id}:${member.role}`;
	const same = $derived(
		visibility !== null &&
			visibility.space_id === before.space_id &&
			membersBefore.length === membersAfter.length &&
			membersAfter.every((member) => membersBefore.some((item) => key(item) === key(member)))
	);
	const spaceName = (id: string) => spaceNameFor(id, lookup, session.user?.id, '') || id;
	const person = (member: Member) => {
		const name = userName(lookup?.users ?? [], member.user_id);
		return member.role === 'read' ? m.space_member_reads({ name }) : name;
	};
	const gone = $derived(
		membersBefore.filter((member) => !membersAfter.some((item) => item.user_id === member.user_id))
	);
	const isNew = (member: Member) => !membersBefore.some((item) => item.user_id === member.user_id);
	const names = (members: readonly Member[]) =>
		new Intl.ListFormat(listLocale(), { type: 'conjunction' }).format(members.map(person));
</script>

{#snippet change(old: string | null, next: string | null)}
	<span class="inline-flex flex-wrap items-baseline gap-x-1.5 tabular-nums">
		{#if old === null}
			<span class="text-muted-foreground">{m.value_unset()}</span>
		{:else}
			<span class="text-muted-foreground line-through">{old}</span>
		{/if}
		<span class="text-muted-foreground" aria-hidden="true">→</span>
		<span class={cn(next === null && 'text-muted-foreground')}>{next ?? m.value_unset()}</span>
	</span>
{/snippet}

{#snippet fieldChange(key: string)}
	{#if key === 'tags'}
		{@render tagsChange()}
	{:else}
		{@render change(shown(before, key), shown(after, key))}
	{/if}
{/snippet}

{#snippet tagsChange()}
	<span class="flex flex-wrap gap-1.5">
		{#each removedTags as id (id)}
			<span
				><span class="sr-only">{m.dryrun_removed()}</span><TagChip
					tag={tag(id)}
					size="sm"
					change="removed"
				/></span
			>
		{/each}
		{#each addedTags as id (id)}
			<span
				><span class="sr-only">{m.dryrun_added()}</span><TagChip
					tag={tag(id)}
					size="sm"
					change="added"
				/></span
			>
		{/each}
	</span>
{/snippet}

{#snippet spaceChange(id: string)}
	{@render change(spaceName(before.space_id), spaceName(id))}
{/snippet}

{#snippet people()}
	<span class="flex flex-col gap-1">
		{#each membersAfter as member (member.user_id)}
			<span class="flex flex-wrap items-center gap-1.5">
				{person(member)}
				{#if isNew(member)}<Badge variant="note">{m.dryrun_new()}</Badge>{/if}
			</span>
		{/each}
		{#each gone as member (member.user_id)}
			<span class="flex flex-wrap items-center gap-1.5">
				<span class="text-muted-foreground line-through">{person(member)}</span>
				<Badge variant="muted">{m.dryrun_gone()}</Badge>
			</span>
		{/each}
	</span>
{/snippet}

<div class="flex flex-col gap-4">
	{#if rows.length > 0}
		<DetailList {rows} />
	{/if}
	{#if preview.rules && preview.rules.length > 0}
		<section class="flex flex-col gap-2">
			<SectionTitle size="card" level={3}>
				{preview.rules.length === 1 ? m.dryrun_rules_one() : m.dryrun_rules()}
			</SectionTitle>
			<ul class="flex flex-col gap-2">
				{#each preview.rules as rule (rule.rule_id)}
					<li class={cardVariants({ size: 'sm' })}>
						<span class="font-medium">{rule.name}</span>
						<div class="mt-1">
							<RuleEffects effects={rule.applied} notes={rule.notes} sends={rule.sends} {lookup} />
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
	{#if visibility}
		{#if same}
			<p class="border-t pt-3 text-sm text-muted-foreground">
				{m.dryrun_visible_same({ names: names(membersAfter) })}
			</p>
		{:else}
			<section class="flex flex-col gap-2">
				<SectionTitle size="card" level={3}>{m.dryrun_visible()}</SectionTitle>
				<DetailList
					rows={[
						visibility.space_id === before.space_id
							? [m.dryrun_space_label(), spaceName(visibility.space_id)]
							: [m.dryrun_space_label(), spaceChange, visibility.space_id],
						[m.dryrun_people(), people]
					]}
				/>
			</section>
		{/if}
	{/if}
</div>
