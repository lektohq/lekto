<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import type { Snippet } from 'svelte';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import IconButton from '#lib/components/IconButton.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import SearchSelect from '#lib/components/SearchSelect.svelte';
	import Select from '#lib/components/Select.svelte';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import {
		AFTER,
		AFTER_LABELS,
		complete,
		FIELD_LABELS,
		FIELDS,
		hasValue,
		newCondition,
		OPERATOR_LABELS,
		OPERATORS,
		OPTIONALS,
		PARTS,
		PARTS_LABELS,
		type MailField,
		type MailRuleForm,
		type Optional
	} from '#lib/mail-rules.ts';
	import { folderLabel, type Mailbox } from '#lib/mailboxes.ts';
	import {
		userChoice,
		type DocumentType,
		type Space,
		type UserName
	} from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// The editor of a mail rule (Tobi, 04.11.2026; mock E), in the frame of the document rule's:
	// name and priority, the mailbox it belongs to, the conditions on the mail (all or any), and
	// the actions: what it takes and for whom always, a space, the type of the mail's text and
	// what becomes of the mail on the server where added ("+ Aktion").
	let {
		form,
		mailboxes,
		users,
		spaces,
		types,
		busy = false,
		error = null,
		cancelHref,
		onsubmit
	}: {
		form: MailRuleForm;
		mailboxes: Mailbox[];
		users: UserName[];
		spaces: Space[];
		types: DocumentType[];
		busy?: boolean;
		error?: string | null;
		cancelHref: string;
		onsubmit: () => void;
	} = $props();

	const mailbox = $derived(mailboxes.find((entry) => entry.id === form.mailboxId) ?? null);
	const takes = $derived(form.parts !== 'nothing');
	const MAX_CONDITIONS = 20;

	const OPTIONAL_LABELS: Record<Optional, () => string> = {
		space: m.mail_rule_action_space,
		type: m.mail_rule_action_type,
		after: m.mail_rule_action_after
	};
	const addable = $derived(
		OPTIONALS.filter((item) => !form.shown.includes(item) && (takes || item === 'after'))
	);

	const people = $derived(
		users
			.filter((user) => user.active || user.id === form.userId)
			.map((user) => ({ value: user.id, label: userChoice(user) }))
	);
	/** The person's personal space (empty), and the shared spaces they edit. */
	const places = $derived([
		{ value: '', label: m.mail_rule_space_personal() },
		...spaces
			.filter(
				(space) =>
					space.personal_of === null &&
					(space.id === form.spaceId ||
						space.members.some((item) => item.user_id === form.userId && item.role === 'edit'))
			)
			.map((space) => ({ value: space.id, label: space.name }))
	]);
	const folders = $derived(
		(mailbox?.folders ?? []).map((name) => ({ value: name, label: folderLabel(name) }))
	);

	function changeField(index: number, field: MailField) {
		const condition = form.conditions[index];
		condition.field = field;
		if (!OPERATORS[field].includes(condition.op)) condition.op = OPERATORS[field][0];
		if (field === 'folder') condition.value = folders[0]?.value ?? '';
	}

	function hide(item: Optional) {
		form.shown = form.shown.filter((entry) => entry !== item);
	}
</script>

<form
	class="flex flex-col gap-6"
	novalidate
	onsubmit={(event) => {
		event.preventDefault();
		if (complete(form) && !busy) onsubmit();
	}}
>
	<div class="grid gap-4 sm:grid-cols-[1fr_12rem]">
		<Field.Field>
			<Field.Label for="mail-rule-name">{m.field_name()}</Field.Label>
			<Input id="mail-rule-name" bind:value={form.name} maxlength={200} />
		</Field.Field>
		<Field.Field>
			<Field.Label for="mail-rule-priority">{m.rule_priority()}</Field.Label>
			<Input
				id="mail-rule-priority"
				type="number"
				min={0}
				max={1000}
				step={1}
				bind:value={form.priority}
			/>
			<Field.Description>{m.mail_rule_priority_hint()}</Field.Description>
		</Field.Field>
	</div>

	<Field.Field>
		<Field.Label for="mail-rule-mailbox">{m.mail_rule_mailbox()}</Field.Label>
		<Select
			id="mail-rule-mailbox"
			bind:value={form.mailboxId}
			options={mailboxes.map((entry) => ({ value: entry.id, label: entry.name }))}
		/>
	</Field.Field>

	<section class="flex flex-col gap-3" aria-labelledby="mail-rule-conditions">
		<SectionTitle id="mail-rule-conditions">{m.rule_conditions()}</SectionTitle>
		<div class="flex flex-col gap-3 rounded-2xl border bg-card p-3" role="group">
			<Select
				aria-label={m.rule_mode()}
				value={form.any ? 'any' : 'all'}
				options={[
					{ value: 'all', label: m.mail_rule_mode_all() },
					{ value: 'any', label: m.mail_rule_mode_any() }
				]}
				onchange={(mode) => (form.any = mode === 'any')}
				class="w-full sm:w-56"
			/>
			{#each form.conditions as condition, index (condition.key)}
				<div class="flex flex-col gap-2 rounded-xl border bg-background p-3">
					<div class="flex flex-wrap items-start gap-2">
						<Select
							aria-label={m.rule_condition_subject()}
							value={condition.field}
							options={FIELDS.map((field) => ({ value: field, label: FIELD_LABELS[field]() }))}
							onchange={(field) => changeField(index, field as MailField)}
							class="w-full sm:w-44"
						/>
						<Select
							aria-label={m.rule_condition_operator()}
							bind:value={condition.op}
							options={OPERATORS[condition.field].map((op) => ({
								value: op,
								label: OPERATOR_LABELS[op]()
							}))}
							class="w-full sm:w-40"
						/>
						{#if condition.field === 'folder'}
							<Select
								aria-label={m.rule_condition_value()}
								bind:value={condition.value}
								options={folders}
								class="min-w-0 flex-1 basis-48"
							/>
						{:else if hasValue(condition.op)}
							<Input
								aria-label={m.rule_condition_value()}
								bind:value={condition.value}
								maxlength={500}
								class="min-w-0 flex-1 basis-48"
							/>
						{/if}
						<IconButton
							label={m.rule_remove()}
							onclick={() => form.conditions.splice(index, 1)}
							class="ml-auto"
						>
							<Trash2 aria-hidden="true" />
						</IconButton>
					</div>
				</div>
			{/each}
			{#if form.conditions.length === 0}
				<p class="text-sm text-muted-foreground">{m.mail_rule_every_hint()}</p>
			{/if}
			<div>
				<Button
					variant="outline"
					size="sm"
					disabled={form.conditions.length >= MAX_CONDITIONS}
					onclick={() => form.conditions.push(newCondition())}
				>
					<Plus aria-hidden="true" />
					{m.rule_add_condition()}
				</Button>
			</div>
		</div>
	</section>

	<section class="flex flex-col gap-3" aria-labelledby="mail-rule-actions">
		<SectionTitle id="mail-rule-actions">{m.rule_actions()}</SectionTitle>
		{#snippet row(label: string, optional: Optional | null, content: Snippet)}
			<div class="flex flex-col gap-2 rounded-xl border bg-background p-3">
				<div class="flex flex-wrap items-start gap-2">
					<span class="w-full pt-2 text-sm font-medium sm:w-44">{label}</span>
					<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">{@render content()}</div>
					{#if optional}
						<IconButton label={m.rule_remove()} onclick={() => hide(optional)}>
							<Trash2 aria-hidden="true" />
						</IconButton>
					{/if}
				</div>
			</div>
		{/snippet}

		{#snippet parts()}
			<Select
				aria-label={m.mail_rule_action_parts()}
				bind:value={form.parts}
				options={PARTS.map((value) => ({ value, label: PARTS_LABELS[value]() }))}
			/>
		{/snippet}
		{@render row(m.mail_rule_action_parts(), null, parts)}

		{#if takes}
			{#snippet person()}
				<SearchSelect
					id="mail-rule-user"
					title={m.mail_rule_action_user()}
					bind:value={form.userId}
					options={people}
					placeholder={m.value_unset()}
					noneLabel={m.value_unset()}
				/>
			{/snippet}
			{@render row(m.mail_rule_action_user(), null, person)}
		{/if}

		{#if takes && form.shown.includes('space')}
			{#snippet place()}
				<Select
					aria-label={m.mail_rule_action_space()}
					bind:value={form.spaceId}
					options={places}
				/>
			{/snippet}
			{@render row(m.mail_rule_action_space(), 'space', place)}
		{/if}

		{#if takes && form.shown.includes('type')}
			{#snippet type()}
				<Select
					aria-label={m.mail_rule_action_type()}
					bind:value={form.typeId}
					options={[
						{ value: '', label: m.mail_rule_type_auto() },
						...types.map((entry) => ({ value: entry.id, label: entry.name }))
					]}
				/>
			{/snippet}
			{@render row(m.mail_rule_action_type(), 'type', type)}
		{/if}

		{#if form.shown.includes('after')}
			{#snippet after()}
				<div class="flex flex-wrap gap-2">
					<Select
						aria-label={m.mail_rule_action_after()}
						bind:value={form.after}
						options={AFTER.map((value) => ({ value, label: AFTER_LABELS[value]() }))}
						class="w-full sm:w-56"
					/>
					{#if form.after === 'move'}
						<Input
							aria-label={m.mail_rule_move_to()}
							placeholder={m.mail_rule_move_to()}
							bind:value={form.moveTo}
							maxlength={1000}
							class="min-w-0 flex-1 basis-48"
						/>
					{/if}
				</div>
			{/snippet}
			{@render row(m.mail_rule_action_after(), 'after', after)}
		{/if}

		{#if addable.length > 0}
			<div>
				<DropdownMenu.Root>
					<DropdownMenu.Trigger class={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}>
						<Plus aria-hidden="true" />
						{m.rule_add_action()}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="start" class="w-64">
						{#each addable as item (item)}
							<DropdownMenu.Item onSelect={() => (form.shown = [...form.shown, item])}
								>{OPTIONAL_LABELS[item]()}</DropdownMenu.Item
							>
						{/each}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		{/if}
	</section>

	<div class="flex flex-col gap-3 border-t pt-4">
		{#if error}<Field.Error>{error}</Field.Error>{/if}
		<div class="flex flex-wrap justify-end gap-2">
			<a href={cancelHref} class={cn(buttonVariants({ variant: 'ghost' }))}>{m.cancel()}</a>
			<Button type="submit" disabled={busy || !complete(form)}>{m.save()}</Button>
		</div>
	</div>
</form>
