<script lang="ts">
	import HintLabel from '#lib/components/HintLabel.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { LIMITS } from '#lib/rules/model.ts';

	// The head of the editor of a rule, a document's or a mail's (web/DESIGN.md, "Mail rules":
	// one set of parts for every rule): its name and its priority, each with its problem.
	// `prefix` names the fields (`<prefix>-name`, `<prefix>-priority`); `priorityInfo` is the
	// help behind the priority's info button, where the kind of rule has more to say about it.
	let {
		name = $bindable(),
		priority = $bindable(),
		errors,
		prefix,
		priorityInfo
	}: {
		name: string;
		/** A number, or what stands in the field while it is typed. */
		priority: number | string;
		errors: Record<string, string>;
		prefix: string;
		priorityInfo?: string;
	} = $props();
</script>

<div class="grid gap-4 sm:grid-cols-[1fr_12rem]">
	<Field.Field>
		<Field.Label for="{prefix}-name">{m.field_name()}</Field.Label>
		<Input
			id="{prefix}-name"
			bind:value={name}
			maxlength={LIMITS.name}
			aria-invalid={errors.name ? true : undefined}
			aria-describedby={errors.name ? `${prefix}-name-error` : undefined}
		/>
		{#if errors.name}<Field.Error id={`${prefix}-name-error`}>{errors.name}</Field.Error>{/if}
	</Field.Field>
	<Field.Field>
		{#if priorityInfo}
			<HintLabel for="{prefix}-priority" label={m.rule_priority()} hint={priorityInfo} />
		{:else}
			<Field.Label for="{prefix}-priority">{m.rule_priority()}</Field.Label>
		{/if}
		<Input
			id="{prefix}-priority"
			type="number"
			min={LIMITS.priorityMin}
			max={LIMITS.priorityMax}
			step={1}
			bind:value={priority}
			aria-invalid={errors.priority ? true : undefined}
			aria-describedby={errors.priority ? `${prefix}-priority-error` : undefined}
		/>
		<Field.Description>{m.rule_priority_hint()}</Field.Description>
		{#if errors.priority}<Field.Error id={`${prefix}-priority-error`}>{errors.priority}</Field.Error
			>{/if}
	</Field.Field>
</div>
