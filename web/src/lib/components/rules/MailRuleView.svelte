<script lang="ts">
	import ConditionTree from '#lib/components/rules/ConditionTree.svelte';
	import {
		actionTexts,
		conditionText,
		treeOf,
		type MailRule,
		type Names
	} from '#lib/mail-rules.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A mail rule to read, as `RuleView` shows a document rule: its mailbox, its conditions in
	// the same tree (`ConditionTree`), its actions.
	let { rule, mailbox, names }: { rule: MailRule; mailbox: string; names: Names } = $props();

	const conditions = $derived(treeOf(rule));
</script>

<dl class="grid gap-x-6 gap-y-4 sm:grid-cols-[10rem_1fr]">
	<dt class="text-sm font-medium text-muted-foreground">{m.mail_rule_mailbox()}</dt>
	<dd>{mailbox}</dd>
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_conditions()}</dt>
	<dd>
		{#if conditions.items.length === 0}
			{m.mail_rule_every_hint()}
		{:else}
			<ConditionTree group={conditions} describe={conditionText} />
		{/if}
	</dd>
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_actions()}</dt>
	<dd>
		<ul class="flex flex-col gap-1.5">
			{#each actionTexts(rule, names) as text, index (index)}
				<li>{text}</li>
			{/each}
		</ul>
	</dd>
</dl>
