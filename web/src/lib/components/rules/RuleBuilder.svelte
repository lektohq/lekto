<script lang="ts">
	import Select from '#lib/components/Select.svelte';
	import ActionRow from '#lib/components/rules/ActionRow.svelte';
	import AddActionMenu from '#lib/components/rules/AddActionMenu.svelte';
	import RuleFormFoot from '#lib/components/rules/RuleFormFoot.svelte';
	import RuleFormHead from '#lib/components/rules/RuleFormHead.svelte';
	import ConditionGroup, { type RowMoves } from '#lib/components/rules/ConditionGroup.svelte';
	import ConditionRow from '#lib/components/rules/ConditionRow.svelte';
	import HintLabel from '#lib/components/HintLabel.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import type { Lookup } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { ACTION_LABELS, TRIGGER_LABELS } from '#lib/rules/describe.ts';
	import { Choice } from '#lib/components/ui/choice/index.ts';
	import {
		ACTION_TYPES,
		LIMITS,
		TRIGGERS,
		asksBefore,
		canAddCondition,
		canAddGroup,
		move,
		newAction,
		newCondition,
		type ActionType,
		type ConditionNode,
		type RuleModel
	} from '#lib/rules/model.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';

	// The form of a rule: name, priority, when it runs, its conditions and actions. The page
	// saves it; `errors` are by key (see `validate` and `saveErrors`). It does not save while a
	// period's text cannot be read (`unreadable`, by key): the model then is not what is shown.
	let {
		model,
		place = '',
		places = [],
		onplace,
		placeHint,
		lookup,
		targets,
		errors,
		general,
		busy,
		cancelHref,
		oncancel,
		onsubmit
	}: {
		model: RuleModel;
		/** Where the rule belongs: `global` or a space; editing it may move it. */
		place?: string;
		/** The places to choose from; fewer than two: no choice. */
		places?: readonly { value: string; label: string }[];
		onplace?: (place: string) => void;
		/** Told in the help of the place besides what a place is (editing: who moves it). */
		placeHint?: string;
		lookup: Lookup;
		/** Where the rule may file documents (spaces, hand-overs). */
		targets: readonly { value: string; label: string }[];
		errors: Record<string, string>;
		general: string | null;
		busy: boolean;
		cancelHref: string;
		/** "Cancel" was chosen: the changes are dropped on purpose (no question on leaving). */
		oncancel?: () => void;
		onsubmit: () => void;
	} = $props();

	const asks = $derived(model.actions.some((action) => action.type === 'ask_webhook'));
	let unreadable = $state<Record<string, boolean>>({});
	const blocked = $derived(Object.values(unreadable).some(Boolean));

	function mark(key: string, cannotRead: boolean) {
		unreadable[key] = cannotRead;
	}

	function add(type: ActionType) {
		model.actions.push(newAction(type));
	}

	function toggleTrigger(trigger: (typeof TRIGGERS)[number], on: boolean) {
		model.triggers = on
			? [...model.triggers, trigger]
			: model.triggers.filter((entry) => entry !== trigger);
	}
</script>

<form
	class="flex flex-col gap-6"
	novalidate
	onsubmit={(event) => {
		event.preventDefault();
		if (blocked) return;
		onsubmit();
	}}
>
	<RuleFormHead bind:name={model.name} bind:priority={model.priority} {errors} prefix="rule" />

	{#if places.length > 1}
		<Field.Field>
			<HintLabel
				for="rule-scope"
				label={m.rule_scope()}
				hint={placeHint ? `${m.rule_scope_hint()} ${placeHint}` : m.rule_scope_hint()}
			/>
			<Select
				id="rule-scope"
				value={place}
				options={places}
				onchange={(value) => onplace?.(value)}
			/>
		</Field.Field>
	{/if}

	<fieldset class="flex flex-col gap-2">
		<legend class="mb-2 text-sm font-medium">{m.rule_triggers()}</legend>
		{#each TRIGGERS as trigger (trigger)}
			<Choice
				checked={model.triggers.includes(trigger)}
				onchange={(event) => toggleTrigger(trigger, event.currentTarget.checked)}
			>
				{TRIGGER_LABELS[trigger]()}
			</Choice>
		{/each}
		{#if asks}<p class="text-sm text-muted-foreground">{m.rule_triggers_ask_hint()}</p>{/if}
		{#if errors.triggers}<Field.Error>{errors.triggers}</Field.Error>{/if}
	</fieldset>

	<section class="flex flex-col gap-3" aria-labelledby="rule-conditions">
		<SectionTitle id="rule-conditions">{m.rule_conditions()}</SectionTitle>
		{#snippet conditionRow(condition: ConditionNode, moves: RowMoves)}
			<ConditionRow
				{condition}
				{lookup}
				error={errors[condition.key]}
				{...moves}
				onunreadable={(unreadable) => mark(condition.key, unreadable)}
			/>
		{/snippet}
		<ConditionGroup
			group={model.conditions}
			root
			{errors}
			row={conditionRow}
			newCondition={() => newCondition('contact')}
			canAddCondition={canAddCondition(model)}
			canAddGroup={(group) => canAddGroup(model, group)}
		/>
	</section>

	<section class="flex flex-col gap-3" aria-labelledby="rule-actions">
		<SectionTitle id="rule-actions">{m.rule_actions()}</SectionTitle>
		{#each model.actions as action, index (action.key)}
			<ActionRow
				{action}
				{lookup}
				{targets}
				{model}
				{errors}
				steps={asksBefore(model, index)}
				error={errors[action.key]}
				onunreadable={(unreadable) => mark(action.key, unreadable)}
				onconditionunreadable={mark}
				onremove={() => model.actions.splice(index, 1)}
				onup={index > 0 ? () => move(model.actions, index, -1) : undefined}
				ondown={index < model.actions.length - 1 ? () => move(model.actions, index, 1) : undefined}
			/>
		{/each}
		<AddActionMenu
			groups={[
				{
					items: ACTION_TYPES.map((type) => ({
						key: type,
						label: ACTION_LABELS[type](),
						onselect: () => add(type)
					}))
				}
			]}
			disabled={model.actions.length >= LIMITS.actions}
		/>
		{#if errors.actions}<Field.Error>{errors.actions}</Field.Error>{/if}
	</section>

	<RuleFormFoot error={general} held={busy || blocked} {cancelHref} {oncancel} />
</form>
