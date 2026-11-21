<script lang="ts">
	import AddActionMenu from '#lib/components/rules/AddActionMenu.svelte';
	import RuleFormFoot from '#lib/components/rules/RuleFormFoot.svelte';
	import MailValueInput from '#lib/components/rules/MailValueInput.svelte';
	import RuleFormHead from '#lib/components/rules/RuleFormHead.svelte';
	import ConditionGroup, { type RowMoves } from '#lib/components/rules/ConditionGroup.svelte';
	import RuleRow from '#lib/components/rules/RuleRow.svelte';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import SearchSelect from '#lib/components/SearchSelect.svelte';
	import Select from '#lib/components/Select.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import {
		addableSteps,
		ENDING,
		STEP_LABELS,
		withStep,
		canAddCondition,
		canAddGroup,
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
	import { folderLabel, LIMITS as MAILBOX_LIMITS, type Mailbox } from '#lib/mailboxes.ts';
	import {
		userChoice,
		type DocumentType,
		type Space,
		type UserName
	} from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { LIMITS } from '#lib/rules/model.ts';
	import { move } from '#lib/rules/tree.ts';

	// The editor of a mail rule (Tobi, 04.11.2026; mock E), in the frame of the document rule's:
	// name and priority, the mailbox it belongs to, the conditions on the mail in the tree every
	// rule has (`ConditionGroup`: groups of all or any, turned around or not), and
	// the actions: what it takes and for whom always, a space and the type of the mail's text
	// where added ("+ Aktion"), and the steps on the mail on the server in order (a move or
	// the trash last). `errors` are by key as `validate` gives them (name, priority, mailbox,
	// user, a condition's, a group's or a step's key); `error` is the line above the buttons.
	let {
		form,
		mailboxes,
		users,
		spaces,
		types,
		errors = {},
		busy = false,
		error = null,
		cancelHref,
		oncancel,
		onsubmit
	}: {
		form: MailRuleForm;
		mailboxes: Mailbox[];
		users: UserName[];
		spaces: Space[];
		types: DocumentType[];
		errors?: Record<string, string>;
		busy?: boolean;
		error?: string | null;
		cancelHref: string;
		oncancel?: () => void;
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

	const people = $derived(
		users
			.filter((user) => user.active || user.id === form.userId)
			.map((user) => ({ value: user.id, label: userChoice(user) }))
	);
	/** The person's personal space (empty), and the shared spaces they edit. */
	const editable = $derived(
		spaces
			.filter(
				(space) =>
					space.personal_of === null &&
					space.members.some((item) => item.user_id === form.userId && item.role === 'edit')
			)
			.map((space) => ({ value: space.id, label: space.name }))
	);
	// A space the person does not edit (another person was chosen since): kept and named, but
	// saving needs another choice, as `ActionRow` says it.
	const unreachable = $derived(
		form.spaceId !== '' && !editable.some((entry) => entry.value === form.spaceId)
	);
	const places = $derived([
		{ value: '', label: m.mail_rule_space_personal() },
		...editable,
		...(unreachable ? [{ value: form.spaceId, label: m.rule_space_unreachable() }] : [])
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

	function hide(item: Optional) {
		form.shown = form.shown.filter((entry) => entry !== item);
	}
</script>

<form
	class="flex flex-col gap-6"
	novalidate
	onsubmit={(event) => {
		event.preventDefault();
		if (!busy) onsubmit();
	}}
>
	<RuleFormHead
		bind:name={form.name}
		bind:priority={form.priority}
		{errors}
		prefix="mail-rule"
		priorityInfo={m.mail_rule_priority_info()}
	/>

	<Field.Field>
		<Field.Label for="mail-rule-mailbox">{m.mail_rule_mailbox()}</Field.Label>
		<Select
			id="mail-rule-mailbox"
			bind:value={form.mailboxId}
			options={mailboxes.map((entry) => ({ value: entry.id, label: entry.name }))}
			aria-invalid={errors.mailbox ? true : undefined}
		/>
		{#if errors.mailbox}<Field.Error>{errors.mailbox}</Field.Error>{/if}
	</Field.Field>

	<section class="flex flex-col gap-3" aria-labelledby="mail-rule-conditions">
		<SectionTitle id="mail-rule-conditions">{m.rule_conditions()}</SectionTitle>
		{#snippet conditionRow(condition: MailConditionNode, moves: RowMoves)}
			{@const invalid = Boolean(errors[condition.key])}
			<RuleRow key={condition.key} error={errors[condition.key]} moves {...moves}>
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
							aria-invalid={invalid || undefined}
							bind:value={condition.value}
							options={folders}
						/>
					{:else if condition.field === 'importance' || condition.field === 'flag' || condition.field === 'keyword'}
						<MailValueInput
							trait={condition.field}
							label={m.rule_condition_value()}
							{invalid}
							value={condition.value}
							keywords={mailbox?.status.keywords ?? []}
							onchange={(next) => (condition.value = next)}
						/>
					{:else}
						<Input
							aria-label={m.rule_condition_value()}
							aria-invalid={invalid || undefined}
							bind:value={condition.value}
							maxlength={LIMITS.text}
						/>
					{/if}
				</div>
			</RuleRow>
		{/snippet}
		<ConditionGroup
			group={form.conditions}
			root
			{errors}
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
			<RuleRow label={m.mail_rule_action_user()} error={errors.user}>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					<SearchSelect
						id="mail-rule-user"
						aria-label={m.mail_rule_action_user()}
						aria-invalid={errors.user ? true : undefined}
						title={m.mail_rule_action_user()}
						bind:value={form.userId}
						options={people}
						placeholder={m.rule_choose()}
					/>
				</div>
			</RuleRow>
		{/if}

		{#if takes && form.shown.includes('space')}
			<RuleRow
				label={m.rule_action_set_space()}
				error={errors.space}
				onremove={() => hide('space')}
			>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					<Select
						aria-label={m.rule_action_set_space()}
						aria-invalid={errors.space ? true : undefined}
						bind:value={form.spaceId}
						options={places}
					/>
					{#if unreachable}
						<p class="text-sm text-muted-foreground">{m.rule_space_unreachable_hint()}</p>
					{/if}
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
			{@const invalid = Boolean(errors[step.key])}
			<RuleRow
				label={STEP_LABELS[step.action]()}
				error={errors[step.key]}
				moves={!ends}
				onup={!ends && index > 0 ? () => move(form.steps, index, -1) : undefined}
				ondown={!ends && index < last ? () => move(form.steps, index, 1) : undefined}
				onremove={() => form.steps.splice(index, 1)}
			>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-2">
					{#if step.action === 'flag' || step.action === 'add_keyword' || step.action === 'remove_keyword'}
						<MailValueInput
							trait={step.action === 'flag' ? 'flag' : 'keyword'}
							label={STEP_LABELS[step.action]()}
							{invalid}
							value={step.value}
							keywords={mailbox?.status.keywords ?? []}
							onchange={(next) => (step.value = next)}
						/>
					{:else if step.action === 'move'}
						<Input
							aria-label={m.mail_rule_move_to()}
							aria-invalid={invalid || undefined}
							placeholder={m.mail_rule_move_to()}
							bind:value={step.value}
							maxlength={MAILBOX_LIMITS.folder}
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
			<AddActionMenu
				groups={[
					{
						items: addable.map((item) => ({
							key: item,
							label: OPTIONAL_LABELS[item](),
							onselect: () => (form.shown = [...form.shown, item])
						}))
					},
					{
						label: m.mail_rule_action_after(),
						items: steps.map((action) => ({
							key: action,
							label: STEP_LABELS[action](),
							onselect: () => (form.steps = withStep(form.steps, action))
						}))
					}
				]}
			/>
		{/if}
	</section>

	<RuleFormFoot {error} held={busy} {cancelHref} {oncancel} />
</form>
