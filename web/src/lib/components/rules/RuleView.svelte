<script lang="ts">
	import ConditionTree from '#lib/components/rules/ConditionTree.svelte';
	import TemplateText from '#lib/components/templates/TemplateText.svelte';
	import type { Lookup } from '#lib/masterdata.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import {
		TRIGGER_LABELS,
		actionTemplate,
		describeAction,
		describeCondition
	} from '#lib/rules/describe.ts';
	import { fromApi, type ApiDefinition, type ConditionNode } from '#lib/rules/model.ts';

	// A rule (or one of its versions) to read: when it runs, its conditions and actions.
	let { definition, lookup }: { definition: ApiDefinition; lookup: Lookup | null } = $props();

	const model = $derived(fromApi(definition));

	const describe = (condition: ConditionNode) => describeCondition(condition, lookup);
</script>

<dl class="grid gap-x-6 gap-y-4 sm:grid-cols-[10rem_1fr]">
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_triggers()}</dt>
	<dd>{model.triggers.map((trigger) => TRIGGER_LABELS[trigger]()).join(' · ')}</dd>
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_conditions()}</dt>
	<dd><ConditionTree group={model.conditions} {describe} /></dd>
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_actions()}</dt>
	<dd>
		<ul class="flex flex-col gap-1.5">
			{#each model.actions as action (action.key)}
				{@const template = actionTemplate(action, lookup)}
				<li>
					{#if template}
						{template.lead}<TemplateText
							text={template.template}
							class="rounded bg-muted px-1 py-0.5 text-meta"
						/>
					{:else if action.type === 'condition'}
						{describeAction(action, lookup)}
						<ConditionTree group={action.conditions} {describe} />
					{:else}
						{describeAction(action, lookup)}
					{/if}
				</li>
			{/each}
		</ul>
	</dd>
</dl>
