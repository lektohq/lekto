<script lang="ts">
	import { actionTexts, conditionTexts, type MailRule, type Names } from '#lib/mail-rules.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A mail rule to read, as `RuleView` shows a document rule: its mailbox, its conditions
	// (all or at least one of them), its actions.
	let { rule, mailbox, names }: { rule: MailRule; mailbox: string; names: Names } = $props();

	const conditions = $derived(conditionTexts(rule));
</script>

<dl class="grid gap-x-6 gap-y-4 sm:grid-cols-[10rem_1fr]">
	<dt class="text-sm font-medium text-muted-foreground">{m.mail_rule_mailbox()}</dt>
	<dd>{mailbox}</dd>
	<dt class="text-sm font-medium text-muted-foreground">{m.rule_conditions()}</dt>
	<dd>
		{#if conditions.length === 0}
			{m.mail_rule_every_hint()}
		{:else}
			<div class="flex flex-col gap-1.5">
				<span class="text-sm text-muted-foreground"
					>{rule.any ? m.rule_group_any() : m.rule_group_all()}</span
				>
				<ul class="flex flex-col gap-1.5 border-l-2 pl-3">
					{#each conditions as text, index (index)}
						<li>{text}</li>
					{/each}
				</ul>
			</div>
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
