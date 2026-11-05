<script lang="ts">
	import Plus from '@lucide/svelte/icons/plus';
	import HintLabel from '#lib/components/HintLabel.svelte';
	import ConditionGroup, { type RowMoves } from '#lib/components/rules/ConditionGroup.svelte';
	import RuleRow from '#lib/components/rules/RuleRow.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import SearchSelect from '#lib/components/SearchSelect.svelte';
	import Select from '#lib/components/Select.svelte';
	import { Button, buttonVariants } from '#lib/components/ui/button/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import {
		addableSteps,
		ENDING,
		STEP_LABELS,
		withStep,
		canAddCondition,
		canAddGroup,
		complete,
		FIELD_LABELS,
		firstValue,
		FIELDS,
		hasValue,
		newCondition,
		operatorText,
		OPERATORS,
		OPTIONALS,
		PARTS,
		PARTS_LABELS,
		type MailConditionNode,
		type MailField,
		type MailRuleForm,
		type Optional
	} from '#lib/mail-rules.ts';
	import { withChoice } from '#lib/components/rules/options.ts';
	import { flagOptions, importanceOptions, isKeyword, keywordOptions } from '#lib/mail-traits.ts';
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
	// name and priority, the mailbox it belongs to, the conditions on the mail in the tree every
	// rule has (`ConditionGroup`: groups of all or any, turned around or not), and
	// the actions: what it takes and for whom always, a space and the type of the mail's text
	// where added ("+ Aktion"), and the steps on the mail on the server in order (a move or
	// the trash last).
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

	const OPTIONAL_LABELS: Record<Optional, () => string> = {
		space: m.rule_action_set_space,
		type: m.mail_rule_action_type
	};
	const addable = $derived(takes ? OPTIONALS.filter((item) => !form.shown.includes(item)) : []);
	const steps = $derived(addableSteps(form.steps));

	function moveStep(index: number, by: -1 | 1) {
		const [item] = form.steps.splice(index, 1);
		form.steps.splice(index + by, 0, item);
	}

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

	function changeField(condition: MailConditionNode, field: MailField) {
		const choice = ['folder', 'importance', 'flag', 'keyword'];
		condition.field = field;
		if (!OPERATORS[field].includes(condition.op)) condition.op = OPERATORS[field][0];
		if (choice.includes(field)) {
			condition.value = firstValue(
				field,
				folders.map((item) => item.value)
			);
		}
	}

	/** A keyword of the mailbox's folders, or one typed that IMAP can carry. */
	async function useKeyword(name: string) {
		const value = name.trim();
		return isKeyword(value) ? { value, label: value } : null;
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
			<HintLabel
				for="mail-rule-priority"
				label={m.rule_priority()}
				hint={m.mail_rule_priority_info()}
			/>
			<Input
				id="mail-rule-priority"
				type="number"
				min={0}
				max={1000}
				step={1}
				bind:value={form.priority}
			/>
			<Field.Description>{m.rule_priority_hint()}</Field.Description>
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
		{#snippet conditionRow(condition: MailConditionNode, moves: RowMoves)}
			<RuleRow key={condition.key} moves {...moves}>
				<Select
					aria-label={m.rule_condition_subject()}
					value={condition.field}
					options={FIELDS.map((field) => ({ value: field, label: FIELD_LABELS[field]() }))}
					onchange={(field) => changeField(condition, field as MailField)}
					class="w-full sm:w-44"
				/>
				<Select
					aria-label={m.rule_condition_operator()}
					bind:value={condition.op}
					options={OPERATORS[condition.field].map((op) => ({
						value: op,
						label: operatorText(condition.field, op)
					}))}
					class="w-full sm:w-48"
				/>
				<div class="min-w-0 flex-1 basis-56">
					{#if !hasValue(condition.op)}
						<span class="sr-only">{m.rule_no_value()}</span>
					{:else if condition.field === 'folder'}
						<Select
							aria-label={m.rule_condition_value()}
							bind:value={condition.value}
							options={folders}
						/>
					{:else if condition.field === 'importance'}
						<Select
							aria-label={m.rule_condition_value()}
							bind:value={condition.value}
							options={importanceOptions()}
						/>
					{:else if condition.field === 'flag'}
						<Select
							aria-label={m.rule_condition_value()}
							bind:value={condition.value}
							options={withChoice(flagOptions(), condition.value)}
						/>
					{:else if condition.field === 'keyword'}
						<SearchSelect
							aria-label={m.rule_condition_value()}
							title={m.mail_keyword_title()}
							bind:value={condition.value}
							options={keywordOptions(mailbox?.status.keywords ?? [], condition.value)}
							placeholder={m.rule_choose()}
							create={useKeyword}
							createLabel={m.mail_keyword_use}
						/>
					{:else}
						<Input
							aria-label={m.rule_condition_value()}
							bind:value={condition.value}
							maxlength={500}
						/>
					{/if}
				</div>
			</RuleRow>
		{/snippet}
		<ConditionGroup
			group={form.conditions}
			root
			errors={{}}
			row={conditionRow}
			newCondition={() => newCondition()}
			canAddCondition={canAddCondition(form)}
			canAddGroup={(group) => canAddGroup(form, group)}
			empty={m.mail_rule_every_hint()}
		/>
	</section>

	<section class="flex flex-col gap-3" aria-labelledby="mail-rule-actions">
		<SectionTitle id="mail-rule-actions">{m.rule_actions()}</SectionTitle>

		<RuleRow label={m.mail_rule_action_parts()}>
			<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
				<Select
					aria-label={m.mail_rule_action_parts()}
					bind:value={form.parts}
					options={PARTS.map((value) => ({ value, label: PARTS_LABELS[value]() }))}
				/>
			</div>
		</RuleRow>

		{#if takes}
			<RuleRow label={m.mail_rule_action_user()}>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					<SearchSelect
						id="mail-rule-user"
						title={m.mail_rule_action_user()}
						bind:value={form.userId}
						options={people}
						placeholder={m.value_unset()}
						noneLabel={m.value_unset()}
					/>
				</div>
			</RuleRow>
		{/if}

		{#if takes && form.shown.includes('space')}
			<RuleRow label={m.rule_action_set_space()} onremove={() => hide('space')}>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					<Select
						aria-label={m.rule_action_set_space()}
						bind:value={form.spaceId}
						options={places}
					/>
				</div>
			</RuleRow>
		{/if}

		{#if takes && form.shown.includes('type')}
			<RuleRow label={m.mail_rule_action_type()} onremove={() => hide('type')}>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					<SearchSelect
						id="mail-rule-type"
						aria-label={m.mail_rule_action_type()}
						title={m.picker_title_type()}
						bind:value={form.typeId}
						options={types.map((entry) => ({ value: entry.id, label: entry.name }))}
						placeholder={m.mail_rule_type_auto()}
						noneLabel={m.mail_rule_type_auto()}
					/>
				</div>
			</RuleRow>
		{/if}

		<!-- What becomes of the mail on the server, step by step (Tobi, 05.11.2026): a move or
		the trash ends the list, so it stays last and does not move. -->
		{#each form.steps as step, index (step.key)}
			{@const ends = ENDING.includes(step.action)}
			{@const last = form.steps.findLastIndex((item) => !ENDING.includes(item.action))}
			<RuleRow
				label={STEP_LABELS[step.action]()}
				moves={!ends}
				onup={!ends && index > 0 ? () => moveStep(index, -1) : undefined}
				ondown={!ends && index < last ? () => moveStep(index, 1) : undefined}
				onremove={() => form.steps.splice(index, 1)}
			>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					{#if step.action === 'flag'}
						<Select
							aria-label={STEP_LABELS[step.action]()}
							bind:value={step.value}
							options={flagOptions()}
						/>
					{:else if step.action === 'add_keyword' || step.action === 'remove_keyword'}
						<SearchSelect
							aria-label={STEP_LABELS[step.action]()}
							title={m.mail_keyword_title()}
							bind:value={step.value}
							options={keywordOptions(mailbox?.status.keywords ?? [], step.value)}
							placeholder={m.rule_choose()}
							create={useKeyword}
							createLabel={m.mail_keyword_use}
						/>
					{:else if step.action === 'move'}
						<Input
							aria-label={m.mail_rule_move_to()}
							placeholder={m.mail_rule_move_to()}
							bind:value={step.value}
							maxlength={1000}
						/>
					{:else}
						<span class="sr-only">{m.rule_no_value()}</span>
					{/if}
				</div>
			</RuleRow>
		{/each}
		{#if form.steps.length > 0}
			<p class="text-sm text-muted-foreground">{m.mail_rule_steps_hint()}</p>
		{/if}

		{#if addable.length > 0 || steps.length > 0}
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
						{#if steps.length > 0}
							{#if addable.length > 0}<DropdownMenu.Separator />{/if}
							<DropdownMenu.Label>{m.mail_rule_action_after()}</DropdownMenu.Label>
							{#each steps as action (action)}
								<DropdownMenu.Item onSelect={() => (form.steps = withStep(form.steps, action))}
									>{STEP_LABELS[action]()}</DropdownMenu.Item
								>
							{/each}
						{/if}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</div>
		{/if}
	</section>

	<div class="flex flex-col gap-3 border-t pt-4">
		{#if error}<Field.Error>{error}</Field.Error>{/if}
		<p class="text-sm text-muted-foreground">{m.rule_save_hint()}</p>
		<div class="flex flex-wrap justify-end gap-2">
			<a href={cancelHref} class={cn(buttonVariants({ variant: 'ghost' }))}>{m.cancel()}</a>
			<Button type="submit" disabled={busy || !complete(form)}>{m.rule_save()}</Button>
		</div>
	</div>
</form>
